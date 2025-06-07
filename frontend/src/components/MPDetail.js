import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { parliamentApi } from '../services/parliamentApi';

function MPDetail() {
  const { mpSlug } = useParams();
  const navigate = useNavigate();
  const [mp, setMp] = useState(null);
  const [mpDetails, setMpDetails] = useState(null);
  const [votes, setVotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [votesLoading, setVotesLoading] = useState(false);
  const [hasSpecificVotes, setHasSpecificVotes] = useState(false);
  const [loadingMoreVotes, setLoadingMoreVotes] = useState(false);
  const [hasMoreVotes, setHasMoreVotes] = useState(true);
  const [votesOffset, setVotesOffset] = useState(0);
  const [loadingFromApi, setLoadingFromApi] = useState(false);
  const [activeTab, setActiveTab] = useState('votes');
  const [selectedSession, setSelectedSession] = useState('current');
  const [availableSessions, setAvailableSessions] = useState([]);

  useEffect(() => {
    loadMP();
  }, [mpSlug]);

  // Extract available sessions from votes and set current session as default
  useEffect(() => {
    if (votes && votes.length > 0) {
      const sessions = [...new Set(votes.map(vote => vote.session))].sort().reverse();
      setAvailableSessions(sessions);
      
      // Set current session as default if not already set
      if (selectedSession === 'current' && sessions.length > 0) {
        setSelectedSession(sessions[0]); // Most recent session first
      }
    }
  }, [votes]);

  // Load all votes when a specific session is selected
  useEffect(() => {
    if (selectedSession !== 'all' && selectedSession !== 'current' && mp && hasMoreVotes && !loadingMoreVotes) {
      // When a specific session is selected, automatically load more votes to get complete session data
      console.log(`Auto-loading more votes for Session ${selectedSession}`);
      loadMoreVotes();
    }
  }, [selectedSession, hasMoreVotes, loadingMoreVotes]);

  // Filter votes by selected session
  const getFilteredVotes = () => {
    if (!votes || votes.length === 0) return [];
    if (selectedSession === 'all') return votes;
    return votes.filter(vote => vote.session === selectedSession);
  };

  const calculateStatistics = () => {
    if (!votes || votes.length === 0 || !hasSpecificVotes) {
      return null;
    }

    const mpParty = mp.current_party?.short_name?.en || mp.memberships?.[0]?.party?.short_name?.en;
    const filteredVotes = getFilteredVotes();
    const votesWithBallot = filteredVotes.filter(vote => vote.mp_ballot);
    
    if (votesWithBallot.length === 0) {
      return null;
    }

    // Basic statistics
    const totalVotes = votesWithBallot.length;
    const yesVotes = votesWithBallot.filter(v => v.mp_ballot === 'Yes').length;
    const noVotes = votesWithBallot.filter(v => v.mp_ballot === 'No').length;
    const abstainedVotes = votesWithBallot.filter(v => v.mp_ballot === 'Paired').length;
    
    // Participation rate
    const participationRate = ((yesVotes + noVotes) / totalVotes) * 100;
    
    // Success rate - votes where MP was on winning side
    const successfulVotes = votesWithBallot.filter(vote => {
      const mpVotedYes = vote.mp_ballot === 'Yes';
      const billPassed = vote.result === 'Passed';
      return (mpVotedYes && billPassed) || (!mpVotedYes && !billPassed);
    }).length;
    const successRate = (successfulVotes / votesWithBallot.length) * 100;
    
    // Bill types analysis
    const billVotes = votesWithBallot.filter(vote => vote.bill_url !== null);
    const motionVotes = votesWithBallot.filter(vote => vote.bill_url === null);
    const governmentBills = billVotes.filter(vote => 
      vote.bill_url && vote.bill_url.includes('/C-')
    );
    const privateBills = billVotes.filter(vote => 
      vote.bill_url && !vote.bill_url.includes('/C-')
    );
    
    // Recent activity (last 20 votes)
    const recentVotes = votesWithBallot.slice(0, Math.min(20, votesWithBallot.length));
    const recentParticipation = recentVotes.filter(v => 
      v.mp_ballot === 'Yes' || v.mp_ballot === 'No'
    ).length;
    const recentParticipationRate = (recentParticipation / recentVotes.length) * 100;

    // Vote distribution by result
    const votesOnPassedBills = votesWithBallot.filter(v => v.result === 'Passed');
    const votesOnFailedBills = votesWithBallot.filter(v => v.result === 'Failed');
    const yesOnPassedBills = votesOnPassedBills.filter(v => v.mp_ballot === 'Yes').length;
    const noOnFailedBills = votesOnFailedBills.filter(v => v.mp_ballot === 'No').length;
    
    // Party line voting calculation using improved heuristics for all parties
    // This estimates how often the MP votes with their party's expected position
    let partyLineVotes = 0;
    let totalPartyLineEligible = 0;
    
    votesWithBallot.forEach(vote => {
      // Skip if we don't have clear yes/no vote
      if (vote.mp_ballot !== 'Yes' && vote.mp_ballot !== 'No') return;
      
      totalPartyLineEligible++;
      
      const votedYes = vote.mp_ballot === 'Yes';
      const billPassed = vote.result === 'Passed';
      const voteMargin = vote.yea_total - vote.nay_total;
      const isCloseVote = Math.abs(voteMargin) < 30;
      const isLandslideVote = Math.abs(voteMargin) > 80;
      
      // Determine if MP likely voted with their party based on party and vote characteristics
      let votedWithParty = false;
      
      if (mpParty === 'Liberal') {
        // Government party: usually supports government bills, especially those that pass
        if (votedYes && billPassed) {
          votedWithParty = true; // Supported successful government initiative
        } else if (!votedYes && !billPassed) {
          votedWithParty = true; // Opposed failed bill (rare but consistent)
        } else if (votedYes && !billPassed && isCloseVote) {
          votedWithParty = true; // Supported government bill that narrowly failed
        }
      } else if (mpParty === 'Conservative') {
        // Main opposition: usually opposes government bills but supports popular measures
        if (!votedYes && billPassed && !isLandslideVote) {
          votedWithParty = true; // Opposed government bill (typical Conservative position)
        } else if (!votedYes && !billPassed) {
          votedWithParty = true; // Opposed bill that failed
        } else if (votedYes && billPassed && isLandslideVote) {
          votedWithParty = true; // Supported popular bipartisan measure
        }
      } else if (mpParty === 'NDP') {
        // Social democratic opposition: often supports progressive bills, opposes conservative ones
        if (votedYes && billPassed && voteMargin > 0) {
          votedWithParty = true; // Supported progressive/social policy that passed
        } else if (!votedYes && !billPassed) {
          votedWithParty = true; // Opposed conservative bill that failed
        } else if (!votedYes && billPassed && isCloseVote) {
          votedWithParty = true; // Opposed government bill on principle
        }
      } else if (mpParty === 'Bloc' || mpParty === 'Bloc Québécois') {
        // Quebec-focused party: supports measures benefiting Quebec, opposes those that don't
        if (!votedYes && billPassed && !isLandslideVote) {
          votedWithParty = true; // Opposed non-Quebec focused bill
        } else if (votedYes && billPassed && isLandslideVote) {
          votedWithParty = true; // Supported popular measure
        } else if (!votedYes && !billPassed) {
          votedWithParty = true; // Opposed bill that failed
        }
      } else if (mpParty === 'Green') {
        // Environmental focus: supports environmental bills, opposes harmful ones
        if (votedYes && billPassed) {
          votedWithParty = true; // Supported progressive/environmental policy
        } else if (!votedYes && !billPassed) {
          votedWithParty = true; // Opposed harmful policy that failed
        }
      } else {
        // Independent or other parties: assume they vote based on personal conviction
        // Give them benefit of doubt for party line voting
        votedWithParty = true;
      }
      
      if (votedWithParty) {
        partyLineVotes++;
      }
    });
    
    const partyLinePercentage = totalPartyLineEligible > 0 ? 
      (partyLineVotes / totalPartyLineEligible) * 100 : 0;
    
    return {
      totalVotes,
      participationRate,
      successRate,
      partyLinePercentage,
      voteBreakdown: {
        yes: yesVotes,
        no: noVotes,
        abstained: abstainedVotes,
        yesPercentage: (yesVotes / totalVotes) * 100,
        noPercentage: (noVotes / totalVotes) * 100
      },
      billAnalysis: {
        totalBills: billVotes.length,
        totalMotions: motionVotes.length,
        governmentBills: governmentBills.length,
        privateBills: privateBills.length
      },
      effectiveness: {
        yesOnPassedBills,
        noOnFailedBills,
        supportedWinningCauses: yesOnPassedBills,
        opposedLosingCauses: noOnFailedBills
      },
      recentActivity: {
        recentVotesCount: recentVotes.length,
        recentParticipationRate
      },
      mpParty
    };
  };

  const loadMP = async () => {
    try {
      const mpUrl = `/politicians/${mpSlug}/`;
      const data = await parliamentApi.getMP(mpUrl);
      console.log('MP data loaded:', data); // Debug log
      setMp(data);
      setMpDetails(data);
      
      // Clear any cached MP votes to ensure fresh data
      const cacheKey = `mp-votes-${mpSlug}-20-0`;
      parliamentApi.clearCacheKey(cacheKey);
      
      loadRecentVotes(mpUrl);
    } catch (error) {
      console.error('Error loading MP:', error);
      setLoading(false);
    }
  };

  const loadMoreVotes = async () => {
    if (!mp || loadingMoreVotes || !hasMoreVotes) return;
    
    try {
      setLoadingMoreVotes(true);
      const mpUrl = `/politicians/${mpSlug}/`;
      const newOffset = votesOffset + 20;
      
      const data = await parliamentApi.getMPVotes(mpUrl, 20, newOffset);
      
      if (data.objects && data.objects.length > 0) {
        // Append new votes to existing ones
        setVotes(prevVotes => [...prevVotes, ...data.objects]);
        setVotesOffset(newOffset + data.objects.length);
        
        // Check if we should continue loading more votes
        if (data.from_api) {
          // When loading from API, only stop if we get fewer than requested
          setLoadingFromApi(true);
          if (data.objects.length < 20) {
            setHasMoreVotes(false);
            console.log('API returned fewer than 20 votes, no more available');
          }
        } else {
          // When loading from cache, check cache limits
          const totalVotesAfterUpdate = votes.length + data.objects.length;
          if (data.total_cached && totalVotesAfterUpdate >= data.total_cached) {
            // Don't stop here - let it try to fetch from API next time
            console.log(`Reached cached limit: ${totalVotesAfterUpdate}/${data.total_cached}, will try API next`);
          } else if (data.objects.length < 20) {
            setHasMoreVotes(false);
            console.log('Received fewer than 20 votes from cache, no more available');
          }
        }
        
        // Update hasSpecificVotes if we find MP ballot data
        if (data.objects.some(vote => vote.mp_ballot)) {
          setHasSpecificVotes(true);
        }
      } else {
        setHasMoreVotes(false);
        console.log('No votes returned, stopping pagination');
      }
    } catch (error) {
      console.error('Error loading more votes:', error);
    } finally {
      setLoadingMoreVotes(false);
    }
  };

  const loadRecentVotes = async (mpUrl, retryCount = 0) => {
    try {
      if (retryCount === 0) {
        setVotesLoading(true);
        setVotesOffset(0);
        setHasMoreVotes(true);
        // Start with general votes immediately for better UX
        try {
          const fallbackData = await parliamentApi.getVotes(20);
          setVotes(fallbackData.objects);
          setHasSpecificVotes(false);
        } catch (fallbackError) {
          console.error('Error loading fallback votes:', fallbackError);
        }
      }
      
      const data = await parliamentApi.getMPVotes(mpUrl, 20);
      
      // Check if votes are being loaded in background
      if (data.loading && retryCount < 20) {
        const delay = retryCount < 5 ? 3000 : retryCount < 10 ? 5000 : 10000; // Gradual backoff
        console.log(`MP votes loading in background, retrying in ${delay/1000} seconds... (attempt ${retryCount + 1}/20)`);
        setTimeout(() => {
          loadRecentVotes(mpUrl, retryCount + 1);
        }, delay);
        return;
      }
      
      if (data.objects && data.objects.length > 0 && data.objects.some(vote => vote.mp_ballot)) {
        // We have MP-specific voting data
        console.log('Loaded MP-specific votes with ballot information');
        setVotes(data.objects);
        setHasSpecificVotes(true);
        setVotesLoading(false);
        setVotesOffset(data.objects.length);
        // Check if there are more votes to load based on total cached
        if (data.total_cached && data.objects.length >= data.total_cached) {
          setHasMoreVotes(false);
        } else if (data.objects.length < 20) {
          setHasMoreVotes(false);
        }
      } else if (data.objects && data.objects.length > 0 && !data.loading) {
        // We have votes but no MP ballot info - this might be the final state
        console.log('Loaded votes without MP ballot information');
        setVotes(data.objects);
        setHasSpecificVotes(false);
        setVotesLoading(false);
        setVotesOffset(data.objects.length);
        if (data.total_cached && data.objects.length >= data.total_cached) {
          setHasMoreVotes(false);
        } else if (data.objects.length < 20) {
          setHasMoreVotes(false);
        }
      } else if (retryCount >= 20) {
        // After 20 retries, stop trying but keep the general votes we loaded initially
        console.log('Max retries reached, keeping general parliamentary votes');
        setVotesLoading(false);
      }
    } catch (error) {
      console.error('Error loading MP votes:', error);
      if (retryCount === 0) {
        // Only fallback on first attempt, subsequent retries will use what we already have
        try {
          const fallbackData = await parliamentApi.getVotes(20);
          setVotes(fallbackData.objects);
          setHasSpecificVotes(false);
        } catch (fallbackError) {
          console.error('Error loading fallback votes:', fallbackError);
        }
      }
    } finally {
      if (retryCount === 0 || retryCount >= 20) {
        setLoading(false);
        if (retryCount >= 20) {
          setVotesLoading(false);
        }
      }
    }
  };

  const renderStatistics = () => {
    const stats = calculateStatistics();
    
    if (!stats) {
      return (
        <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
          <h3>Statistics Not Available</h3>
          <p>Statistics will be available once we have voting data for {mp.name}.</p>
          {!hasSpecificVotes && (
            <p style={{ fontSize: '14px', marginTop: '10px' }}>
              Voting records are still being loaded in the background.
            </p>
          )}
        </div>
      );
    }

    return (
      <div style={{ padding: '20px 0' }}>
        {/* Overview Cards */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '20px',
          marginBottom: '30px'
        }}>
          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '20px',
            borderRadius: '8px',
            border: '1px solid #dee2e6',
            textAlign: 'center'
          }}>
            <h3 style={{ margin: '0 0 10px 0', color: '#495057' }}>Total Votes</h3>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#495057' }}>
              {stats.totalVotes}
            </div>
            <div style={{ fontSize: '14px', color: '#6c757d', marginTop: '5px' }}>
              Votes with recorded position
            </div>
          </div>

          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '20px',
            borderRadius: '8px',
            border: '1px solid #dee2e6',
            textAlign: 'center'
          }}>
            <h3 style={{ margin: '0 0 10px 0', color: '#495057' }}>Participation Rate</h3>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#495057' }}>
              {Math.round(stats.participationRate)}%
            </div>
            <div style={{ fontSize: '14px', color: '#6c757d', marginTop: '5px' }}>
              Voted yes or no (vs abstained)
            </div>
          </div>

          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '20px',
            borderRadius: '8px',
            border: '1px solid #dee2e6',
            textAlign: 'center'
          }}>
            <h3 style={{ margin: '0 0 10px 0', color: '#495057' }}>Success Rate</h3>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#495057' }}>
              {Math.round(stats.successRate)}%
            </div>
            <div style={{ fontSize: '14px', color: '#6c757d', marginTop: '5px' }}>
              Voted on winning side
            </div>
          </div>

          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '20px',
            borderRadius: '8px',
            border: '1px solid #dee2e6',
            textAlign: 'center'
          }}>
            <h3 style={{ margin: '0 0 10px 0', color: '#495057' }}>Party Line Voting</h3>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#495057' }}>
              {Math.round(stats.partyLinePercentage)}%
            </div>
            <div style={{ fontSize: '14px', color: '#6c757d', marginTop: '5px' }}>
              Voted along party lines
            </div>
          </div>

          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '20px',
            borderRadius: '8px',
            border: '1px solid #dee2e6',
            textAlign: 'center'
          }}>
            <h3 style={{ margin: '0 0 10px 0', color: '#495057' }}>Recent Activity</h3>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#495057' }}>
              {Math.round(stats.recentActivity.recentParticipationRate)}%
            </div>
            <div style={{ fontSize: '14px', color: '#6c757d', marginTop: '5px' }}>
              Last {stats.recentActivity.recentVotesCount} votes
            </div>
          </div>
        </div>

        {/* Detailed Breakdowns */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '30px' }}>
          {/* Vote Breakdown */}
          <div style={{
            backgroundColor: 'white',
            padding: '25px',
            borderRadius: '8px',
            border: '1px solid #dee2e6',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
          }}>
            <h3 style={{ margin: '0 0 20px 0', color: '#495057' }}>Vote Distribution</h3>
            
            <div style={{ marginBottom: '15px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <span style={{ color: '#28a745', fontWeight: '600' }}>✓ Yes Votes</span>
                <span style={{ fontWeight: 'bold' }}>{stats.voteBreakdown.yes} ({Math.round(stats.voteBreakdown.yesPercentage)}%)</span>
              </div>
              <div style={{
                height: '8px',
                backgroundColor: '#e9ecef',
                borderRadius: '4px',
                overflow: 'hidden'
              }}>
                <div style={{
                  height: '100%',
                  width: `${stats.voteBreakdown.yesPercentage}%`,
                  backgroundColor: '#28a745'
                }}></div>
              </div>
            </div>

            <div style={{ marginBottom: '15px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <span style={{ color: '#dc3545', fontWeight: '600' }}>✗ No Votes</span>
                <span style={{ fontWeight: 'bold' }}>{stats.voteBreakdown.no} ({Math.round(stats.voteBreakdown.noPercentage)}%)</span>
              </div>
              <div style={{
                height: '8px',
                backgroundColor: '#e9ecef',
                borderRadius: '4px',
                overflow: 'hidden'
              }}>
                <div style={{
                  height: '100%',
                  width: `${stats.voteBreakdown.noPercentage}%`,
                  backgroundColor: '#dc3545'
                }}></div>
              </div>
            </div>

            {stats.voteBreakdown.abstained > 0 && (
              <div style={{ marginBottom: '15px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                  <span style={{ color: '#6c757d', fontWeight: '600' }}>⚖️ Abstained</span>
                  <span style={{ fontWeight: 'bold' }}>{stats.voteBreakdown.abstained}</span>
                </div>
              </div>
            )}
          </div>

          {/* Bill Analysis */}
          <div style={{
            backgroundColor: 'white',
            padding: '25px',
            borderRadius: '8px',
            border: '1px solid #dee2e6',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
          }}>
            <h3 style={{ margin: '0 0 20px 0', color: '#495057' }}>Legislative Focus</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#495057' }}>📜 Bills</span>
                <span style={{ fontWeight: 'bold', color: '#007bff' }}>{stats.billAnalysis.totalBills}</span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingLeft: '15px' }}>
                <span style={{ color: '#6c757d', fontSize: '14px' }}>Government Bills (C-*)</span>
                <span style={{ fontWeight: '600' }}>{stats.billAnalysis.governmentBills}</span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingLeft: '15px' }}>
                <span style={{ color: '#6c757d', fontSize: '14px' }}>Private Bills</span>
                <span style={{ fontWeight: '600' }}>{stats.billAnalysis.privateBills}</span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#495057' }}>🗳️ Motions</span>
                <span style={{ fontWeight: 'bold', color: '#6610f2' }}>{stats.billAnalysis.totalMotions}</span>
              </div>
            </div>
          </div>

          {/* Effectiveness Analysis */}
          <div style={{
            backgroundColor: 'white',
            padding: '25px',
            borderRadius: '8px',
            border: '1px solid #dee2e6',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
          }}>
            <h3 style={{ margin: '0 0 20px 0', color: '#495057' }}>Legislative Effectiveness</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#28a745' }}>✓ Supported Winning Causes</span>
                <span style={{ fontWeight: 'bold', color: '#28a745' }}>{stats.effectiveness.supportedWinningCauses}</span>
              </div>
              
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#dc3545' }}>✗ Opposed Losing Causes</span>
                <span style={{ fontWeight: 'bold', color: '#dc3545' }}>{stats.effectiveness.opposedLosingCauses}</span>
              </div>
              
              <div style={{ 
                marginTop: '10px', 
                padding: '10px', 
                backgroundColor: '#f8f9fa', 
                borderRadius: '4px',
                fontSize: '14px',
                color: '#495057'
              }}>
                <strong>Effectiveness Score:</strong> {Math.round(stats.successRate)}% of votes were on the winning side
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  if (loading || !mp) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        Loading MP details...
      </div>
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <button 
        onClick={() => navigate('/')}
        style={{ 
          marginBottom: '20px',
          padding: '10px 20px', 
          backgroundColor: '#6c757d', 
          color: 'white', 
          border: 'none', 
          borderRadius: '4px',
          cursor: 'pointer'
        }}
      >
        ← Back to MP List
      </button>

      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '20px', 
        marginBottom: '30px',
        padding: '20px',
        backgroundColor: '#f8f9fa',
        borderRadius: '8px'
      }}>
        {mp.image && (
          <img 
            src={`https://openparliament.ca${mp.image}`}
            alt={mp.name}
            style={{ 
              width: '120px', 
              height: '120px', 
              borderRadius: '50%', 
              objectFit: 'cover' 
            }}
          />
        )}
        <div>
          <h1 style={{ margin: '0 0 10px 0' }}>{mp.name}</h1>
          <p style={{ margin: '5px 0', fontSize: '18px', color: '#007bff' }}>
            {mp.current_party?.short_name?.en || mp.memberships?.[0]?.party?.short_name?.en}
          </p>
          <p style={{ margin: '5px 0', fontSize: '16px', color: '#666' }}>
            {mp.current_riding?.name?.en || mp.memberships?.[0]?.riding?.name?.en}
            {(mp.current_riding?.province || mp.memberships?.[0]?.riding?.province) ? 
              `, ${mp.current_riding?.province || mp.memberships?.[0]?.riding?.province}` : ''}
          </p>
          {mpDetails?.email && (
            <p style={{ margin: '5px 0', fontSize: '14px' }}>
              Email: <a href={`mailto:${mpDetails.email}`}>{mpDetails.email}</a>
            </p>
          )}
        </div>
      </div>

      {/* Tab Navigation */}
      <div style={{ 
        borderBottom: '2px solid #dee2e6',
        marginBottom: '20px',
        marginTop: '30px'
      }}>
        <div style={{ display: 'flex', gap: '0' }}>
          <button
            onClick={() => setActiveTab('votes')}
            style={{
              padding: '12px 24px',
              border: 'none',
              backgroundColor: 'transparent',
              color: activeTab === 'votes' ? '#333' : '#666',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: activeTab === 'votes' ? '600' : 'normal',
              borderBottom: activeTab === 'votes' ? '2px solid #333' : '2px solid transparent',
              marginBottom: '-2px',
              transition: 'all 0.2s ease'
            }}
            onMouseEnter={(e) => {
              if (activeTab !== 'votes') {
                e.target.style.color = '#333';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'votes') {
                e.target.style.color = '#666';
              }
            }}
          >
            📊 Voting Record
          </button>
          <button
            onClick={() => setActiveTab('statistics')}
            style={{
              padding: '12px 24px',
              border: 'none',
              backgroundColor: 'transparent',
              color: activeTab === 'statistics' ? '#333' : '#666',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: activeTab === 'statistics' ? '600' : 'normal',
              borderBottom: activeTab === 'statistics' ? '2px solid #333' : '2px solid transparent',
              marginBottom: '-2px',
              transition: 'all 0.2s ease'
            }}
            onMouseEnter={(e) => {
              if (activeTab !== 'statistics') {
                e.target.style.color = '#333';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'statistics') {
                e.target.style.color = '#666';
              }
            }}
          >
            📈 Statistics
          </button>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'votes' && (
        <div>
          <div style={{ marginBottom: '30px' }}>
            <h2 style={{ margin: '0 0 20px 0' }}>
              {selectedSession === 'all' 
                ? `${mp.name}'s Voting Record`
                : `${mp.name}'s Voting Record for Session ${selectedSession}`
              }
            </h2>
            
            {/* Session Selector */}
            {availableSessions.length > 1 && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '15px', 
                marginBottom: '25px',
                flexWrap: 'wrap'
              }}>
                <label style={{ 
                  fontSize: '14px', 
                  color: '#666', 
                  fontWeight: '500',
                  minWidth: 'fit-content'
                }}>
                  Session:
                </label>
                <select
                  value={selectedSession}
                  onChange={(e) => setSelectedSession(e.target.value)}
                  style={{
                    padding: '8px 12px',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    backgroundColor: 'white',
                    fontSize: '14px',
                    color: '#333',
                    cursor: 'pointer',
                    outline: 'none',
                    fontFamily: 'inherit'
                  }}
                >
                  <option value="all">All</option>
                  {availableSessions.map(session => (
                    <option key={session} value={session}>
                      {session}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          
          <p style={{ color: '#666', marginBottom: '20px' }}>
            {hasSpecificVotes ? (
              <>
                Showing how {mp.name} voted on parliamentary matters
                {selectedSession !== 'all' && ` in Session ${selectedSession}`}.
                <span style={{ color: '#0969da' }}> Click any vote to see detailed party statistics and all MP votes.</span>
              </>
            ) : (
              <>
                Recent parliamentary votes
                {selectedSession !== 'all' && ` from Session ${selectedSession}`}. 
                {votes.length > 0 && <span style={{ color: '#0969da' }}> Click any vote to see detailed party statistics and all MP votes.</span>}
              </>
            )}
          </p>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {getFilteredVotes().map((vote) => {
            const isOppositionMotion = vote.description?.en?.toLowerCase().includes('opposition motion');
            const isBillVote = vote.bill_url !== null;
            const isCommitteeReport = vote.description?.en?.toLowerCase().includes('committee');
            const isConfidenceVote = vote.description?.en?.toLowerCase().includes('confidence');
            
            let voteCategory = 'Parliamentary Motion';
            if (isBillVote) voteCategory = 'Bill';
            else if (isCommitteeReport) voteCategory = 'Committee Report';
            else if (isOppositionMotion) voteCategory = 'Opposition Motion';
            else if (isConfidenceVote) voteCategory = 'Confidence Vote';
            
            return (
              <div 
                key={vote.url}
                onClick={() => {
                  // Extract vote ID from URL like "/votes/45-1/4/" -> "45-1/4"
                  const voteId = vote.url.replace('/votes/', '').replace(/\/$/, '');
                  // URL encode the vote ID to handle slashes
                  const encodedVoteId = encodeURIComponent(voteId);
                  console.log('Navigating to vote:', voteId, 'encoded as:', encodedVoteId, 'from URL:', vote.url);
                  navigate(`/vote/${encodedVoteId}`);
                }}
                style={{
                  border: '1px solid #ddd',
                  borderRadius: '8px',
                  padding: '20px',
                  backgroundColor: 'white',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                  cursor: 'pointer',
                  transition: 'box-shadow 0.2s, transform 0.1s'
                }}
                onMouseEnter={(e) => {
                  e.target.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
                  e.target.style.transform = 'translateY(-1px)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
                  e.target.style.transform = 'translateY(0)';
                }}
              >
                <div style={{ marginBottom: '15px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                    <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                      <div style={{ 
                        padding: '4px 8px', 
                        backgroundColor: '#e9ecef', 
                        borderRadius: '4px', 
                        fontSize: '12px',
                        fontWeight: 'bold',
                        color: '#495057'
                      }}>
                        {voteCategory}
                      </div>
                      
                      {vote.mp_ballot ? (
                        <div style={{ 
                          padding: '6px 12px', 
                          borderRadius: '4px',
                          backgroundColor: vote.mp_ballot === 'Yes' ? '#d4edda' : vote.mp_ballot === 'No' ? '#f8d7da' : '#fff3cd',
                          color: vote.mp_ballot === 'Yes' ? '#155724' : vote.mp_ballot === 'No' ? '#721c24' : '#856404',
                          fontWeight: 'bold',
                          fontSize: '14px',
                          border: '2px solid',
                          borderColor: vote.mp_ballot === 'Yes' ? '#28a745' : vote.mp_ballot === 'No' ? '#dc3545' : '#ffc107'
                        }}>
                          {mp.name} voted: {vote.mp_ballot}
                        </div>
                      ) : !hasSpecificVotes ? (
                        <div style={{ 
                          padding: '6px 12px', 
                          borderRadius: '4px',
                          backgroundColor: '#f8f9fa',
                          color: '#6c757d',
                          fontStyle: 'italic',
                          fontSize: '14px',
                          border: '1px dashed #dee2e6'
                        }}>
                          {mp.name}'s vote: Loading...
                        </div>
                      ) : null}
                    </div>
                    
                    <div style={{ 
                      padding: '6px 12px', 
                      borderRadius: '4px',
                      backgroundColor: vote.result === 'Passed' ? '#d4edda' : '#f8d7da',
                      color: vote.result === 'Passed' ? '#155724' : '#721c24',
                      fontWeight: 'bold',
                      fontSize: '14px'
                    }}>
                      {vote.result}
                    </div>
                  </div>
                  
                  <h3 style={{ 
                    margin: '0 0 15px 0', 
                    fontSize: '18px', 
                    lineHeight: '1.4',
                    color: '#333',
                    fontWeight: '600'
                  }}>
                    {vote.description?.en}
                  </h3>
                  
                  {isBillVote && (
                    <div style={{ 
                      marginBottom: '15px',
                      padding: '8px 12px',
                      backgroundColor: '#e7f3ff',
                      borderRadius: '4px',
                      fontSize: '14px',
                      color: '#0969da'
                    }}>
                      📋 <strong>Bill:</strong> {vote.bill_url.replace('/bills/', '').replace('/', ' ')}
                    </div>
                  )}
                  
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '10px'
                  }}>
                    <div style={{ 
                      fontSize: '14px', 
                      color: '#666',
                      display: 'flex',
                      gap: '15px',
                      flexWrap: 'wrap'
                    }}>
                      <span><strong>📅</strong> {vote.date}</span>
                      <span><strong>Session:</strong> {vote.session}</span>
                      <span><strong>Vote #{vote.number}</strong></span>
                    </div>
                    
                    <div style={{ 
                      display: 'flex', 
                      gap: '12px', 
                      fontSize: '13px',
                      backgroundColor: '#f8f9fa',
                      padding: '6px 10px',
                      borderRadius: '4px'
                    }}>
                      <span style={{ color: '#28a745', fontWeight: '600' }}>
                        ✓ {vote.yea_total}
                      </span>
                      <span style={{ color: '#dc3545', fontWeight: '600' }}>
                        ✗ {vote.nay_total}
                      </span>
                      {vote.paired_total > 0 && (
                        <span style={{ color: '#6c757d', fontWeight: '600' }}>
                          ⚖️ {vote.paired_total}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        
        {/* Load More Button - only show if we have more votes AND we're viewing all sessions */}
        {hasMoreVotes && getFilteredVotes().length > 0 && selectedSession === 'all' && (
          <div style={{ textAlign: 'center', marginTop: '30px' }}>
            <button
              onClick={loadMoreVotes}
              disabled={loadingMoreVotes}
              style={{
                padding: '12px 24px',
                backgroundColor: loadingMoreVotes ? '#6c757d' : '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontSize: '16px',
                fontWeight: '500',
                cursor: loadingMoreVotes ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.2s',
                minWidth: '140px'
              }}
              onMouseEnter={(e) => {
                if (!loadingMoreVotes) {
                  e.target.style.backgroundColor = '#0056b3';
                }
              }}
              onMouseLeave={(e) => {
                if (!loadingMoreVotes) {
                  e.target.style.backgroundColor = '#007bff';
                }
              }}
            >
              {loadingMoreVotes ? 'Loading...' : 'Load More Votes'}
            </button>
            <p style={{ 
              marginTop: '10px', 
              color: '#666', 
              fontSize: '14px' 
            }}>
              Showing {getFilteredVotes().length} votes{hasSpecificVotes ? ` with ${mp.name}'s positions` : ''}{selectedSession !== 'all' ? ` from Session ${selectedSession}` : ''}
              {loadingFromApi && <span style={{ color: '#0969da' }}> (now loading from live data)</span>}
            </p>
          </div>
        )}
        
        {/* End of votes message - only show for "all sessions" view when no more votes */}
        {!hasMoreVotes && getFilteredVotes().length > 20 && selectedSession === 'all' && (
          <div style={{ textAlign: 'center', marginTop: '30px' }}>
            <p style={{ color: '#666', fontSize: '14px' }}>
              All available votes loaded ({getFilteredVotes().length} total)
            </p>
          </div>
        )}
        </div>
      )}

      {/* Statistics Tab */}
      {activeTab === 'statistics' && (
        <div>
          <div style={{ marginBottom: '30px' }}>
            <h2 style={{ margin: '0 0 20px 0' }}>
              {selectedSession === 'all' 
                ? `${mp.name}'s Parliamentary Statistics`
                : `${mp.name}'s Parliamentary Statistics for Session ${selectedSession}`
              }
            </h2>
            
            {/* Session Selector */}
            {availableSessions.length > 1 && (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '15px', 
                marginBottom: '25px',
                flexWrap: 'wrap'
              }}>
                <label style={{ 
                  fontSize: '14px', 
                  color: '#666', 
                  fontWeight: '500',
                  minWidth: 'fit-content'
                }}>
                  Session:
                </label>
                <select
                  value={selectedSession}
                  onChange={(e) => setSelectedSession(e.target.value)}
                  style={{
                    padding: '8px 12px',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    backgroundColor: 'white',
                    fontSize: '14px',
                    color: '#333',
                    cursor: 'pointer',
                    outline: 'none',
                    fontFamily: 'inherit'
                  }}
                >
                  <option value="all">All</option>
                  {availableSessions.map(session => (
                    <option key={session} value={session}>
                      {session}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          {renderStatistics()}
        </div>
      )}
    </div>
  );
}

export default MPDetail;