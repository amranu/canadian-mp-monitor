/**
 * Calculate actual party-line voting statistics based on real party majority positions
 */

import { parliamentApi } from '../services/parliamentApi';

/**
 * Calculate party majority position for a specific vote
 * @param {Array} ballots - Array of ballot objects with politician_party and ballot fields
 * @param {string} party - Party name to calculate majority for
 * @returns {Object} Party voting statistics and majority position
 */
export const calculatePartyPosition = (ballots, party) => {
  console.log('Calculating party position for:', party);
  console.log('Sample ballot structure:', ballots[0]);
  
  const partyBallots = ballots.filter(ballot => {
    // Check all possible party field names in the ballot data structure
    let partyName = '';
    
    if (ballot.politician_party) {
      partyName = ballot.politician_party;
    } else if (ballot.party) {
      partyName = ballot.party;
    } else if (ballot.politician?.current_party?.short_name?.en) {
      partyName = ballot.politician.current_party.short_name.en;
    } else if (ballot.politician?.party) {
      partyName = ballot.politician.party;
    }
    
    // If still no party name, log the ballot structure for debugging
    if (!partyName && console.log) {
      console.log('Could not extract party from ballot:', Object.keys(ballot));
    }
    
    const isMatch = partyName.toLowerCase().includes(party.toLowerCase()) ||
           (party === 'Conservative' && (partyName.includes('CPC') || partyName.includes('Conservative'))) ||
           (party === 'Liberal' && partyName.includes('Liberal')) ||
           (party === 'NDP' && partyName.includes('NDP')) ||
           (party === 'Bloc' && partyName.includes('Bloc')) ||
           (party === 'Green' && partyName.includes('Green'));
    
    if (isMatch) {
      console.log('✓ Matched ballot party:', partyName, 'for target:', party);
    }
    
    return isMatch;
  });

  console.log(`Found ${partyBallots.length} ballots for ${party} out of ${ballots.length} total`);

  if (partyBallots.length === 0) {
    return {
      total: 0,
      yes: 0,
      no: 0,
      paired: 0,
      absent: 0,
      majorityPosition: null,
      cohesion: 0
    };
  }

  const voteCounts = {
    yes: partyBallots.filter(b => b.ballot === 'Yes').length,
    no: partyBallots.filter(b => b.ballot === 'No').length,
    paired: partyBallots.filter(b => b.ballot === 'Paired').length,
    absent: partyBallots.filter(b => !b.ballot || b.ballot === 'Absent').length
  };

  const substantiveVotes = voteCounts.yes + voteCounts.no;
  const majorityPosition = voteCounts.yes > voteCounts.no ? 'Yes' : 'No';
  const majorityCount = Math.max(voteCounts.yes, voteCounts.no);
  
  // Calculate party cohesion (how unified the party was)
  const cohesion = substantiveVotes > 0 ? (majorityCount / substantiveVotes) * 100 : 0;

  return {
    total: partyBallots.length,
    yes: voteCounts.yes,
    no: voteCounts.no,
    paired: voteCounts.paired,
    absent: voteCounts.absent,
    majorityPosition: substantiveVotes > 0 ? majorityPosition : null,
    cohesion: Math.round(cohesion * 10) / 10 // Round to 1 decimal place
  };
};

/**
 * Calculate whether an MP voted with their party majority on a specific vote
 * @param {string} mpVote - MP's vote (Yes/No/Paired/etc)
 * @param {string} partyMajorityPosition - Party's majority position (Yes/No)
 * @returns {boolean} True if MP voted with party majority
 */
export const didVoteWithParty = (mpVote, partyMajorityPosition) => {
  if (!partyMajorityPosition || !mpVote) return false;
  if (mpVote !== 'Yes' && mpVote !== 'No') return false; // Skip paired/absent votes
  
  return mpVote === partyMajorityPosition;
};

/**
 * Calculate comprehensive party-line voting statistics for an MP
 * @param {Array} mpVotes - Array of MP's votes with vote details
 * @param {string} mpParty - MP's party affiliation
 * @returns {Object} Comprehensive party-line statistics
 */
export const calculatePartyLineStats = async (mpVotes, mpParty) => {
  let partyLineVotes = 0;
  let totalEligibleVotes = 0;
  let partyDisciplineBreaks = [];
  let partyLoyaltyBySession = {};
  let cohesionStats = [];

  const votesWithDetails = [];

  // Process each vote to get detailed ballot information
  for (const vote of mpVotes) {
    try {
      // Skip if MP didn't cast yes/no vote
      if (vote.mp_ballot !== 'Yes' && vote.mp_ballot !== 'No') continue;

      // Get detailed ballot information for this vote using the ballots endpoint
      const ballotsData = await parliamentApi.getVoteBallots(vote.url);
      if (!ballotsData || !ballotsData.objects || ballotsData.objects.length === 0) {
        console.log('No ballot data for:', vote.url);
        continue;
      }
      
      console.log('Processing vote:', vote.url, 'with', ballotsData.objects.length, 'ballots');

      // Calculate party position for this vote
      const partyStats = calculatePartyPosition(ballotsData.objects, mpParty);
      
      // Skip if party didn't have a clear majority position
      if (!partyStats.majorityPosition) continue;

      totalEligibleVotes++;
      const votedWithParty = didVoteWithParty(vote.mp_ballot, partyStats.majorityPosition);
      
      if (votedWithParty) {
        partyLineVotes++;
      } else {
        // Record party discipline break
        partyDisciplineBreaks.push({
          vote: vote,
          mpVote: vote.mp_ballot,
          partyPosition: partyStats.majorityPosition,
          partyCohesion: partyStats.cohesion,
          voteDescription: vote.description
        });
      }

      // Track session-based stats
      const session = vote.session || 'unknown';
      if (!partyLoyaltyBySession[session]) {
        partyLoyaltyBySession[session] = { partyLine: 0, total: 0 };
      }
      partyLoyaltyBySession[session].total++;
      if (votedWithParty) {
        partyLoyaltyBySession[session].partyLine++;
      }

      // Track cohesion stats
      cohesionStats.push({
        vote: vote.url,
        cohesion: partyStats.cohesion,
        votedWithParty: votedWithParty
      });

      votesWithDetails.push({
        ...vote,
        partyStats,
        votedWithParty
      });

    } catch (error) {
      console.warn(`Error processing vote ${vote.url}:`, error);
      continue;
    }
  }

  // Calculate final statistics
  const partyLinePercentage = totalEligibleVotes > 0 ? 
    Math.round((partyLineVotes / totalEligibleVotes) * 100 * 10) / 10 : 0;

  const avgPartyCohesion = cohesionStats.length > 0 ?
    Math.round((cohesionStats.reduce((sum, stat) => sum + stat.cohesion, 0) / cohesionStats.length) * 10) / 10 : 0;

  // Calculate session percentages
  Object.keys(partyLoyaltyBySession).forEach(session => {
    const stats = partyLoyaltyBySession[session];
    stats.percentage = stats.total > 0 ? 
      Math.round((stats.partyLine / stats.total) * 100 * 10) / 10 : 0;
  });

  return {
    partyLineVotes,
    totalEligibleVotes,
    partyLinePercentage,
    partyDisciplineBreaks: partyDisciplineBreaks.slice(0, 10), // Return up to 10 most recent breaks
    partyLoyaltyBySession,
    avgPartyCohesion,
    votesAnalyzed: votesWithDetails.length,
    methodology: 'actual_party_majority'
  };
};

/**
 * Get party name variations for matching
 * @param {string} party - Primary party name
 * @returns {Array} Array of possible party name variations
 */
export const getPartyVariations = (party) => {
  const variations = {
    'Conservative': ['Conservative', 'CPC', 'Conservative Party', 'Tory'],
    'Liberal': ['Liberal', 'Liberal Party', 'Lib'],
    'NDP': ['NDP', 'New Democratic Party', 'New Democrat'],
    'Bloc': ['Bloc', 'Bloc Québécois', 'BQ'],
    'Green': ['Green', 'Green Party'],
    'Independent': ['Independent', 'Ind.', 'Non-affiliated']
  };

  return variations[party] || [party];
};