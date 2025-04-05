from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import hashlib
from voting_system import ApprovalVotingSystem, Candidate
import os
from werkzeug.utils import secure_filename
import time
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
from pymongo.errors import ConnectionFailure, OperationFailure

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Initialize voting system
voting_system = ApprovalVotingSystem()

# Admin credentials (in production, these should be stored securely)
ADMIN_USERNAME = "HarryPotter"
ADMIN_PASSWORD = "HP2025"

UPLOAD_FOLDER = 'static/symbols'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

load_dotenv()  # Load environment variables from .env file

class MongoConnection:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            MONGO_URI = os.getenv('MONGO_URI')
            cls._instance = MongoClient(
                MONGO_URI,
                maxPoolSize=50,  # Maximum number of connections in the pool
                waitQueueTimeoutMS=2500  # How long to wait for a connection
            )
        return cls._instance

    @classmethod
    def debug_connection(cls):
        mongo_uri = os.getenv('MONGO_URI')
        # Hide password for security
        debug_uri = mongo_uri.replace(
            mongo_uri.split('@')[0].split(':')[1], '****'
        )
        print(f"Attempting to connect to: {debug_uri}")

# Use it in your app
client = MongoConnection.get_instance()
db = client['voting_system']
candidates_collection = db['candidates']
symbols_collection = db['symbols']

def allowed_file(filename):
    return '.' in filename and \
           filename.lower().split('.')[-1] in ALLOWED_EXTENSIONS

# Login decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes for voter interface
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vote', methods=['GET', 'POST'])
def vote():
    if request.method == 'POST':
        voter_id = request.form.get('voter_id')
        candidate_ids = request.form.getlist('candidates[]')
        
        if not voter_id or not candidate_ids:
            flash('Please fill in all fields', 'error')
            return redirect(url_for('vote'))
        
        # Check if voter ID has already voted
        existing_vote = db.votes.find_one({'voter_id': voter_id})
        if existing_vote:
            flash('This Voter ID has already cast a vote!', 'error')
            return redirect(url_for('vote'))
        
        try:
            # Store vote in MongoDB
            vote_data = {
                'voter_id': voter_id,
                'candidate_ids': [ObjectId(cid) for cid in candidate_ids],
                'created_at': time.time()
            }
            db.votes.insert_one(vote_data)
            
            flash('Votes cast successfully!', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            flash(f'Error casting vote: {str(e)}', 'error')
            return redirect(url_for('vote'))
    
    # GET request - show voting page
    try:
        candidates = list(candidates_collection.aggregate([
            {
                '$lookup': {
                    'from': 'symbols',
                    'localField': 'symbol_id',
                    'foreignField': '_id',
                    'as': 'symbol'
                }
            },
            {
                '$unwind': '$symbol'
            }
        ]))
        return render_template('vote.html', candidates=candidates)
    except Exception as e:
        flash(f'Error fetching candidates: {str(e)}', 'error')
        return redirect(url_for('index'))

# Routes for admin interface
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash('Logged in successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/admin/candidates', methods=['GET', 'POST'])
@admin_required
def manage_candidates():
    try:
        if request.method == 'POST':
            name = request.form.get('name')
            symbol = request.form.get('symbol')
            symbol_image = request.files.get('symbol_image')
            
            if symbol_image and allowed_file(symbol_image.filename):
                filename = secure_filename(symbol_image.filename)
                # Generate unique filename using timestamp
                filename = f"{int(time.time())}_{filename}"
                symbol_image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
                # Store symbol in MongoDB
                symbol_data = {
                    'name': symbol,
                    'filename': filename,
                    'created_at': time.time()
                }
                symbol_id = symbols_collection.insert_one(symbol_data).inserted_id
                
                # Store candidate in MongoDB with error handling
                try:
                    candidate_data = {
                        'name': name,
                        'symbol_id': symbol_id,
                        'created_at': time.time()
                    }
                    result = candidates_collection.insert_one(candidate_data)
                    if result.inserted_id:
                        flash('Candidate added successfully!', 'success')
                    else:
                        flash('Failed to add candidate', 'error')
                except OperationFailure as e:
                    flash(f'Database operation failed: {str(e)}', 'error')
            else:
                flash('Invalid image file', 'error')
        
        # Fetch candidates with error handling
        try:
            candidates = list(candidates_collection.aggregate([
                {
                    '$lookup': {
                        'from': 'symbols',
                        'localField': 'symbol_id',
                        'foreignField': '_id',
                        'as': 'symbol'
                    }
                },
                {
                    '$unwind': '$symbol'
                }
            ]))
        except OperationFailure as e:
            candidates = []
            flash(f'Failed to fetch candidates: {str(e)}', 'error')
            
        return render_template('manage_candidates.html', candidates=candidates)
        
    except ConnectionFailure:
        flash('Database connection failed', 'error')
        return redirect(url_for('index'))

@app.route('/admin/candidates/delete/<candidate_id>')
@admin_required
def delete_candidate(candidate_id):
    try:
        # Find candidate to get symbol_id
        candidate = candidates_collection.find_one({'_id': ObjectId(candidate_id)})
        if candidate:
            # Delete symbol file and database entry
            symbol = symbols_collection.find_one({'_id': candidate['symbol_id']})
            if symbol:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], symbol['filename'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                symbols_collection.delete_one({'_id': candidate['symbol_id']})
            
            # Delete candidate
            candidates_collection.delete_one({'_id': ObjectId(candidate_id)})
            flash('Candidate deleted successfully!', 'success')
        else:
            flash('Candidate not found', 'error')
    except Exception as e:
        flash(f'Error deleting candidate: {str(e)}', 'error')
    
    return redirect(url_for('manage_candidates'))

@app.route('/admin/results')
@admin_required
def view_results():
    try:
        # Get all votes
        votes = list(db.votes.find({}))
        
        # Get all candidates with their symbols
        candidates = list(candidates_collection.aggregate([
            {
                '$lookup': {
                    'from': 'symbols',
                    'localField': 'symbol_id',
                    'foreignField': '_id',
                    'as': 'symbol'
                }
            },
            {
                '$unwind': '$symbol'
            }
        ]))
        
        # Calculate results
        results = {}
        for candidate in candidates:
            results[str(candidate['_id'])] = {
                'name': candidate['name'],
                'symbol': candidate['symbol']['name'],
                'votes': 0
            }
        
        # Count votes for each candidate
        total_votes = 0
        for vote in votes:
            total_votes += 1
            for candidate_id in vote['candidate_ids']:
                candidate_id_str = str(candidate_id)
                if candidate_id_str in results:
                    results[candidate_id_str]['votes'] += 1
        
        # Calculate percentages and sort by votes
        sorted_results = []
        for candidate_id, data in results.items():
            percentage = (data['votes'] / total_votes * 100) if total_votes > 0 else 0
            sorted_results.append({
                'name': data['name'],
                'symbol': data['symbol'],
                'votes': data['votes'],
                'percentage': round(percentage, 2)
            })
        
        sorted_results.sort(key=lambda x: x['votes'], reverse=True)
        
        # Generate statistics
        stats = {
            'total_votes': total_votes,
            'total_candidates': len(candidates),
            'highest_votes': sorted_results[0]['votes'] if sorted_results else 0,
            'lowest_votes': sorted_results[-1]['votes'] if sorted_results else 0,
        }
        
        return render_template('results.html', results=sorted_results, stats=stats)
        
    except Exception as e:
        flash(f'Error calculating results: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/reset-votes', methods=['POST'])
@admin_required
def reset_votes():
    try:
        # Delete all votes from the database
        db.votes.delete_many({})
        flash('All votes have been reset successfully!', 'success')
    except Exception as e:
        flash(f'Error resetting votes: {str(e)}', 'error')
    
    return redirect(url_for('view_results'))

# Add this route for resetting candidates
@app.route('/admin/reset-candidates', methods=['POST'])
@admin_required
def reset_candidates():
    try:
        # First, delete all symbol files
        symbols = symbols_collection.find({})
        for symbol in symbols:
            if 'filename' in symbol:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], symbol['filename'])
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        # Delete all symbols from database
        symbols_collection.delete_many({})
        
        # Delete all candidates from database
        candidates_collection.delete_many({})
        
        # Delete all votes since candidates no longer exist
        db.votes.delete_many({})
        
        flash('All candidates have been reset successfully!', 'success')
    except Exception as e:
        flash(f'Error resetting candidates: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

# Create indexes when your app starts
def create_indexes():
    try:
        candidates_collection.create_index('name')
        candidates_collection.create_index('symbol_id')
        symbols_collection.create_index('name')
        # Add unique index for voter_id
        db.votes.create_index('voter_id', unique=True)
        print("Indexes created successfully")
    except Exception as e:
        print(f"Error creating indexes: {e}")

@app.route('/test-db')
def test_db():
    try:
        # Test basic operations
        collections = db.list_collection_names()
        candidates_count = candidates_collection.count_documents({})
        symbols_count = symbols_collection.count_documents({})
        
        return {
            'status': 'success',
            'message': 'Connected to MongoDB Atlas',
            'collections': collections,
            'counts': {
                'candidates': candidates_count,
                'symbols': symbols_count
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Database connection failed: {str(e)}'
        }, 500

@app.route('/debug-candidates')
def debug_candidates():
    candidates = list(candidates_collection.aggregate([
        {
            '$lookup': {
                'from': 'symbols',
                'localField': 'symbol_id',
                'foreignField': '_id',
                'as': 'symbol'
            }
        },
        {
            '$unwind': '$symbol'
        }
    ]))
    return {'candidates': str(candidates)}

# Call this when your app starts
if __name__ == '__main__':
    create_indexes()
    app.run(debug=True)