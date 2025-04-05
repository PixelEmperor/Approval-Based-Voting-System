from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import math

@dataclass
class Candidate:
    id: str
    name: str
    symbol: str
    symbol_image: str = ""  # Path to the symbol image file

@dataclass
class Vote:
    voter_id: str
    candidate_id: str
    timestamp: datetime

class ApprovalVotingSystem:
    def __init__(self):
        self.candidates: Dict[str, Candidate] = {}
        self.votes: List[Vote] = []
        self.voter_registry: Dict[str, bool] = {}  # Tracks who has voted
    
    def add_candidate(self, candidate: Candidate) -> bool:
        """Add a candidate to the election."""
        if candidate.id in self.candidates:
            return False
        self.candidates[candidate.id] = candidate
        return True
    
    def cast_vote(self, voter_id: str, candidate_ids: List[str]) -> Tuple[bool, str]:
        """
        Record votes for multiple candidates.
        Returns (success, message).
        """
        # Verify voter hasn't voted
        if voter_id in self.voter_registry:
            return False, "Voter has already cast a ballot"
            
        # Verify all candidates exist
        for candidate_id in candidate_ids:
            if candidate_id not in self.candidates:
                return False, "Invalid candidate"
            
        # Record votes for each selected candidate
        for candidate_id in candidate_ids:
            vote = Vote(
                voter_id=voter_id,
                candidate_id=candidate_id,
                timestamp=datetime.utcnow()
            )
            self.votes.append(vote)
        
        # Mark voter as having voted
        self.voter_registry[voter_id] = True
        
        return True, "Votes recorded successfully"
    
    def calculate_results(self) -> Dict:
        """
        Calculate election results including:
        - Total votes per candidate
        - Percentage based on total submissions
        - Participation rate
        - Victory margin
        """
        # Total submissions is the number of unique voters
        total_submissions = len(self.voter_registry)
        if total_submissions == 0:
            return {
                "total_votes": 0,
                "total_submissions": 0,
                "candidates": [],
                "participation_rate": 0,
                "victory_margin": 0
            }
        
        # Count votes per candidate
        vote_counts = {}
        for candidate_id in self.candidates:
            vote_counts[candidate_id] = 0
            
        for vote in self.votes:
            vote_counts[vote.candidate_id] += 1
        
        # Calculate percentages and create sorted results
        results = []
        for candidate_id, votes in vote_counts.items():
            candidate = self.candidates[candidate_id]
            # Calculate percentage based on total submissions
            percentage = (votes / total_submissions) * 100
            results.append({
                "candidate_id": candidate_id,
                "name": candidate.name,
                "symbol": candidate.symbol,
                "votes": votes,
                "percentage": round(percentage, 2)
            })
        
        # Sort by vote count descending
        results.sort(key=lambda x: x["votes"], reverse=True)
        
        # Calculate victory margin (difference between top two candidates)
        victory_margin = 0
        if len(results) >= 2:
            victory_margin = results[0]["percentage"] - results[1]["percentage"]
        
        # Calculate participation rate
        registered_voters = len(self.voter_registry)
        participation_rate = 100  # Since each voter in registry has voted
        
        return {
            "total_votes": len(self.votes),
            "total_submissions": total_submissions,
            "candidates": results,
            "participation_rate": round(participation_rate, 2),
            "victory_margin": round(victory_margin, 2)
        }
    
    def get_hourly_voting_pattern(self) -> Dict:
        """Analyze voting patterns by hour."""
        hourly_counts = {}
        
        for vote in self.votes:
            hour = vote.timestamp.hour
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
        
        # Fill in missing hours with zero votes
        for hour in range(24):
            if hour not in hourly_counts:
                hourly_counts[hour] = 0
        
        return dict(sorted(hourly_counts.items()))
    
    def generate_statistics(self) -> Dict:
        """Generate additional voting statistics."""
        total_votes = len(self.votes)
        if total_votes == 0:
            return {
                "total_votes": 0,
                "average_votes_per_candidate": 0,
                "voting_rate": 0
            }
        
        results = self.calculate_results()
        
        # Calculate standard deviation of vote distribution
        votes_list = [candidate["votes"] for candidate in results["candidates"]]
        mean = sum(votes_list) / len(votes_list)
        variance = sum((x - mean) ** 2 for x in votes_list) / len(votes_list)
        std_dev = math.sqrt(variance)
        
        return {
            "total_votes": total_votes,
            "average_votes_per_candidate": round(mean, 2),
            "vote_distribution_std_dev": round(std_dev, 2),
            "voter_turnout": results["participation_rate"],
            "hourly_pattern": self.get_hourly_voting_pattern()
        }

# Example usage and testing


if __name__ == "__main__":
    test_voting_system()