import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { parliamentApi } from '../services/parliamentApi';
import BillCard from './BillCard';
import DebateCard from './DebateCard';
import SEOHead from './SEOHead';

function MPDetail() {
  const { mpSlug } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
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
  const [activeTab, setActiveTab] = useState(() => {
    // Initialize tab from URL params, default to 'votes'
    const tabFromUrl = searchParams.get('tab');
    return ['votes', 'statistics', 'bills', 'debates', 'expenditures'].includes(tabFromUrl) ? tabFromUrl : 'votes';
  });
  const [selectedSession, setSelectedSession] = useState('all');
  const [availableSessions, setAvailableSessions] = useState([]);
  const [sponsoredBills, setSponsoredBills] = useState([]);
  const [billsLoading, setBillsLoading] = useState(false);
  const [partyLineStats, setPartyLineStats] = useState(null);
  const [partyLineLoading, setPartyLineLoading] = useState(false);
  const [partyLineSessions, setPartyLineSessions] = useState(null);
  const [partyLineSessionsLoading, setPartyLineSessionsLoading] = useState(false);
  const [expenditures, setExpenditures] = useState(null);
  const [expendituresLoading, setExpendituresLoading] = useState(false);
  const [debates, setDebates] = useState(null);
  const [debatesLoading, setDebatesLoading] = useState(false);

  // Function to update tab and persist to URL
  const updateActiveTab = (newTab) => {
    setActiveTab(newTab);
    const newSearchParams = new URLSearchParams(searchParams);
    newSearchParams.set('tab', newTab);
    setSearchParams(newSearchParams, { replace: true });
  };

  const getPartyColor = (party) => {
    const colors = {
      'Conservative': '#1e3a8a',
      'Liberal': '#dc2626',
      'NDP': '#ea580c',
      'Bloc': '#06b6d4',
      'Green': '#16a34a',
      'Unknown': '#6b7280'
    };
    return colors[party] || '#6b7280';
  };

  useEffect(() => {
    loadMP();
  }, [mpSlug]);

  // Sync activeTab state with URL parameters (for browser back/forward)
  useEffect(() => {
    const tabFromUrl = searchParams.get('tab');
    if (tabFromUrl && ['votes', 'statistics', 'bills', 'debates', 'expenditures'].includes(tabFromUrl) && tabFromUrl !== activeTab) {
      setActiveTab(tabFromUrl);
    }
  }, [searchParams]); // Removed activeTab dependency to prevent loops

  // Load sponsored bills when component loads to determine if tab should be shown
  useEffect(() => {
    if (mp && sponsoredBills.length === 0 && !billsLoading) {
      loadSponsoredBills();
    }
  }, [mp]);

  // Load party-line statistics when component loads
  useEffect(() => {
    if (mpSlug && !partyLineLoading && !partyLineStats) {
      loadPartyLineStats();
    }
  }, [mpSlug]);

  // Load party-line sessions data when component loads
  useEffect(() => {
    if (!partyLineSessions && !partyLineSessionsLoading) {
      loadPartyLineSessions();
    }
  }, []);

  // Load expenditures when expenditures tab is selected
  useEffect(() => {
    if (activeTab === 'expenditures' && mpSlug && !expenditures && !expendituresLoading) {
      loadExpenditures();
    }
  }, [activeTab, mpSlug]);

  // Load debates when debates tab is selected
  useEffect(() => {
    if (activeTab === 'debates' && mpSlug && !debates && !debatesLoading) {
      loadDebates();
    }
  }, [activeTab, mpSlug]);

  // Extract available sessions from votes
  useEffect(() => {
    if (votes && votes.length > 0) {
      const sessions = [...new Set(votes.map(vote => vote.session))].sort().reverse();
      setAvailableSessions(sessions);
    }
  }, [votes]);


  // Load all votes when a specific session is selected
  useEffect(() => {
    if (selectedSession !== 'all' && mp && !loadingMoreVotes) {
      // When a specific session is selected, load all available votes for that MP
      console.log(`Loading all votes for MP when Session ${selectedSession} is selected`);
      loadAllVotesForMP();
    }
  }, [selectedSession, mp]);

  // Filter votes by selected session
  const getFilteredVotes = () => {
    if (!votes || votes.length === 0) return [];
    if (selectedSession === 'all') return votes;
    return votes.filter(vote => vote.session === selectedSession);
  };

  // Get session-specific party-line statistics
  const getSessionPartyLineStats = () => {
    if (!partyLineStats) return null;
    
    // If 'all' sessions selected, return overall stats
    if (selectedSession === 'all') {
      return {
        percentage: partyLineStats.party_line_percentage,
        votes: partyLineStats.party_line_votes,
        total: partyLineStats.total_eligible_votes,
        label: 'Overall'
      };
    }
    
    // For specific sessions
    const targetSession = selectedSession;
    
    // Get session-specific stats
    const sessionStats = partyLineStats.party_loyalty_by_session?.[targetSession];
    if (sessionStats) {
      return {
        percentage: sessionStats.percentage,
        votes: sessionStats.party_line,
        total: sessionStats.total,
        label: `Session ${targetSession}`
      };
    }
    
    // Fallback to overall if session not found
    return {
      percentage: partyLineStats.party_line_percentage,
      votes: partyLineStats.party_line_votes,
      total: partyLineStats.total_eligible_votes,
      label: 'Overall'
    };
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

    // Basic statistics - exclude Paired votes from total (matches party-line calculation)
    const substantiveVotes = votesWithBallot.filter(v => v.mp_ballot === 'Yes' || v.mp_ballot === 'No');
    const totalVotes = substantiveVotes.length;
    const yesVotes = votesWithBallot.filter(v => v.mp_ballot === 'Yes').length;
    const noVotes = votesWithBallot.filter(v => v.mp_ballot === 'No').length;
    const abstainedVotes = votesWithBallot.filter(v => v.mp_ballot === 'Paired').length;
    
    // Participation rate (substantive votes vs all recorded positions)
    const allRecordedVotes = votesWithBallot.length;
    const participationRate = (totalVotes / allRecordedVotes) * 100;
    
    // Success rate - votes where MP was on winning side (only substantive votes)
    const successfulVotes = substantiveVotes.filter(vote => {
      const mpVotedYes = vote.mp_ballot === 'Yes';
      const billPassed = vote.result === 'Passed';
      return (mpVotedYes && billPassed) || (!mpVotedYes && !billPassed);
    }).length;
    const successRate = (successfulVotes / totalVotes) * 100;
    
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
    
    
    return {
      totalVotes,
      participationRate,
      successRate,
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

  const loadAllVotesForMP = async () => {
    if (!mp || loadingMoreVotes) return;
    
    try {
      setLoadingMoreVotes(true);
      const mpUrl = `/politicians/${mpSlug}/`;
      
      // Load ALL votes for this MP (up to 5000)
      const data = await parliamentApi.getMPVotes(mpUrl, 5000, 0);
      
      if (data.objects && data.objects.length > 0) {
        console.log(`Loaded ${data.objects.length} total votes for ${mpSlug}`);
        setVotes(data.objects);
        setVotesOffset(data.objects.length);
        setHasMoreVotes(data.has_more || false);
        
        // Update hasSpecificVotes if we find MP ballot data
        if (data.objects.some(vote => vote.mp_ballot)) {
          setHasSpecificVotes(true);
        }
      }
    } catch (error) {
      console.error('Error loading all MP votes:', error);
    } finally {
      setLoadingMoreVotes(false);
    }
  };

  const loadMoreVotes = async () => {
    if (!mp || loadingMoreVotes || !hasMoreVotes) return;
    
    try {
      setLoadingMoreVotes(true);
      const mpUrl = `/politicians/${mpSlug}/`;
      const newOffset = votesOffset + 20;
      
      const data = await parliamentApi.getMPVotes(mpUrl, 5000, newOffset);
      
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
      
      const data = await parliamentApi.getMPVotes(mpUrl, 5000, 0);
      
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

  const loadSponsoredBills = async () => {
    try {
      setBillsLoading(true);
      const data = await parliamentApi.getMPSponsoredBills(mp.url);
      setSponsoredBills(data.objects || []);
      console.log(`Loaded ${data.objects?.length || 0} sponsored bills for ${mp.name}`);
      
      // If currently on bills tab but no bills found, switch to votes tab
      if (activeTab === 'bills' && (!data.objects || data.objects.length === 0)) {
        updateActiveTab('votes');
      }
    } catch (error) {
      console.error('Error loading sponsored bills:', error);
      setSponsoredBills([]);
      // If currently on bills tab but error occurred, switch to votes tab
      if (activeTab === 'bills') {
        updateActiveTab('votes');
      }
    } finally {
      setBillsLoading(false);
    }
  };

  const loadPartyLineStats = async () => {
    try {
      setPartyLineLoading(true);
      // Always load all party line stats (not session-specific) to get comprehensive data
      // The session filtering happens in the frontend display logic
      const data = await parliamentApi.getMPPartyLineStats(mpSlug, null);
      setPartyLineStats(data);
      console.log('Party-line stats loaded:', data);
    } catch (error) {
      console.error('Error loading party-line stats:', error);
      // If party-line stats are not available, don't show an error to user
      setPartyLineStats(null);
    } finally {
      setPartyLineLoading(false);
    }
  };

  const loadPartyLineSessions = async () => {
    try {
      setPartyLineSessionsLoading(true);
      const data = await parliamentApi.getPartyLineSessions();
      setPartyLineSessions(data);
      console.log('Party-line sessions loaded:', data);
    } catch (error) {
      console.error('Error loading party-line sessions:', error);
      setPartyLineSessions(null);
    } finally {
      setPartyLineSessionsLoading(false);
    }
  };

  const loadExpenditures = async () => {
    try {
      setExpendituresLoading(true);
      const data = await parliamentApi.getMPExpenditures(mpSlug);
      setExpenditures(data);
      console.log('Expenditures loaded:', data);
    } catch (error) {
      console.error('Error loading expenditures:', error);
      setExpenditures(null);
    } finally {
      setExpendituresLoading(false);
    }
  };

  const loadDebates = async () => {
    try {
      setDebatesLoading(true);
      const data = await parliamentApi.getMPDebates(mpSlug);
      setDebates(data);
      console.log('Debates loaded:', data);
    } catch (error) {
      console.error('Error loading debates:', error);
      setDebates(null);
    } finally {
      setDebatesLoading(false);
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
              Substantive votes (Yes/No only)
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
              Voted yes/no vs paired/abstained
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
            <h3 style={{ margin: '0 0 10px 0', color: '#495057' }}>Recent Activity</h3>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#495057' }}>
              {Math.round(stats.recentActivity.recentParticipationRate)}%
            </div>
            <div style={{ fontSize: '14px', color: '#6c757d', marginTop: '5px' }}>
              Last {stats.recentActivity.recentVotesCount} votes
            </div>
          </div>

          {/* Party-Line Statistics Card */}
          {partyLineStats && (() => {
            const sessionStats = getSessionPartyLineStats();
            return sessionStats && (
              <div style={{
                backgroundColor: '#f8f9fa',
                padding: '20px',
                borderRadius: '8px',
                border: '1px solid #dee2e6',
                textAlign: 'center'
              }}>
                <h3 style={{ margin: '0 0 10px 0', color: '#495057' }}>
                  Party-Line Voting
                  <div style={{ fontSize: '12px', fontWeight: 'normal', color: '#666', marginTop: '4px' }}>
                    {sessionStats.label}
                  </div>
                </h3>
                <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#495057' }}>
                  {sessionStats.percentage}%
                </div>
                <div style={{ fontSize: '14px', color: '#6c757d', marginTop: '5px' }}>
                  Voted with {partyLineStats.mp_party} majority ({sessionStats.votes}/{sessionStats.total} votes)
                </div>
              </div>
            );
          })()}
        </div>

        {/* Party-Line Detailed Stats */}
        {partyLineStats && (
          <div style={{ 
            backgroundColor: 'white',
            padding: '25px',
            borderRadius: '8px',
            border: '1px solid #dee2e6',
            boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
            marginBottom: '30px'
          }}>
            <h3 style={{ margin: '0 0 20px 0', color: '#495057' }}>Party-Line Voting Analysis</h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '20px' }}>
              <div>
                <h4 style={{ margin: '0 0 15px 0', color: '#495057' }}>Overall Statistics</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Party-Line Percentage:</span>
                    <strong>{partyLineStats.party_line_percentage}%</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Votes Analyzed:</span>
                    <strong>{partyLineStats.total_eligible_votes}</strong>
                  </div>
                </div>
              </div>

              {Object.keys(partyLineStats.party_loyalty_by_session).length > 0 && (
                <div>
                  <h4 style={{ margin: '0 0 15px 0', color: '#495057' }}>By Parliamentary Session</h4>
                  <div style={{ 
                    maxHeight: '240px', 
                    overflowY: 'auto',
                    border: '1px solid #e9ecef',
                    borderRadius: '4px',
                    padding: '8px',
                    display: 'flex', 
                    flexDirection: 'column', 
                    gap: '8px', 
                    fontSize: '14px' 
                  }}>
                    {Object.entries(partyLineStats.party_loyalty_by_session)
                      .sort(([a], [b]) => b.localeCompare(a))
                      .map(([session, stats]) => {
                        // Get session average for comparison
                        const sessionAverage = partyLineSessions?.sessions?.[session]?.avg_party_line_percentage;
                        const partyAverage = partyLineSessions?.sessions?.[session]?.party_breakdown?.[partyLineStats.mp_party]?.avg_party_line_percentage;
                        
                        return (
                          <div key={session} style={{ 
                            padding: '8px',
                            backgroundColor: '#f8f9fa',
                            borderRadius: '4px',
                            border: '1px solid #e9ecef'
                          }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                              <span style={{ fontWeight: '600' }}>Session {session}:</span>
                              <strong>{stats.percentage}% ({stats.party_line}/{stats.total})</strong>
                            </div>
                            {(sessionAverage || partyAverage) && (
                              <div style={{ fontSize: '12px', color: '#666' }}>
                                {partyAverage && (
                                  <span style={{ marginRight: '10px' }}>
                                    Party avg: {partyAverage}%
                                    {stats.percentage > partyAverage && <span style={{ color: '#28a745' }}> ↑</span>}
                                    {stats.percentage < partyAverage && <span style={{ color: '#dc3545' }}> ↓</span>}
                                  </span>
                                )}
                                {sessionAverage && (
                                  <span>
                                    Overall avg: {sessionAverage}%
                                    {stats.percentage > sessionAverage && <span style={{ color: '#28a745' }}> ↑</span>}
                                    {stats.percentage < sessionAverage && <span style={{ color: '#dc3545' }}> ↓</span>}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}

              {partyLineStats.party_discipline_breaks && partyLineStats.party_discipline_breaks.length > 0 && (
                <div>
                  <h4 style={{ margin: '0 0 15px 0', color: '#495057' }}>
                    Recent Party Discipline Breaks ({partyLineStats.party_discipline_breaks.length})
                  </h4>
                  <div style={{ 
                    maxHeight: '240px', 
                    overflowY: 'auto',
                    border: '1px solid #e9ecef',
                    borderRadius: '4px',
                    padding: '8px'
                  }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                      {partyLineStats.party_discipline_breaks.map((break_, index) => (
                        <div 
                          key={index} 
                          onClick={() => {
                            // Convert vote_id format from "45-1_4" to "45-1/4" for navigation
                            const voteId = break_.vote_id.replace(/_/g, '/');
                            const encodedVoteId = encodeURIComponent(voteId);
                            console.log('Navigating to party discipline break vote:', voteId, 'encoded as:', encodedVoteId, 'from vote_id:', break_.vote_id);
                            navigate(`/vote/${encodedVoteId}`);
                          }}
                          style={{ 
                            padding: '8px',
                            backgroundColor: '#fff3cd',
                            borderRadius: '4px',
                            border: '1px solid #ffeaa7',
                            cursor: 'pointer',
                            transition: 'background-color 0.2s, transform 0.1s'
                          }}
                          onMouseEnter={(e) => {
                            e.target.style.backgroundColor = '#ffecb3';
                            e.target.style.transform = 'translateY(-1px)';
                          }}
                          onMouseLeave={(e) => {
                            e.target.style.backgroundColor = '#fff3cd';
                            e.target.style.transform = 'translateY(0)';
                          }}
                        >
                          <div style={{ fontWeight: 'bold', marginBottom: '2px' }}>
                            {break_.date} - Voted {break_.mp_vote} (Party: {break_.party_position})
                          </div>
                          <div style={{ color: '#6c757d' }}>
                            {break_.description?.length > 80 
                              ? break_.description.substring(0, 80) + '...' 
                              : break_.description}
                          </div>
                          <div style={{ fontSize: '11px', color: '#856404', marginTop: '4px', fontStyle: 'italic' }}>
                            Click to view vote details →
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

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

  // Generate structured data for the MP
  const mpJsonLd = mp ? {
    "@context": "https://schema.org",
    "@type": "Person",
    "name": mp.name,
    "jobTitle": "Member of Parliament",
    "affiliation": {
      "@type": "PoliticalParty",
      "name": mp.current_party?.name?.en || "Unknown Party"
    },
    "workLocation": {
      "@type": "Place",
      "name": mp.current_riding?.name?.en || "Unknown Riding",
      "address": {
        "@type": "PostalAddress",
        "addressRegion": mp.current_riding?.province || "Unknown Province",
        "addressCountry": "CA"
      }
    },
    "memberOf": {
      "@type": "GovernmentOrganization",
      "name": "Parliament of Canada"
    },
    "url": `https://mptracker.ca/mp/${mpSlug}`
  } : null;

  return (
    <>
      {mp && (
        <SEOHead 
          title={`${mp.name} - MP for ${mp.current_riding?.name?.en || 'Unknown Riding'} | Canadian MP Tracker`}
          description={`View ${mp.name}'s voting record, sponsored bills, and parliamentary activity. ${mp.current_party?.name?.en || 'MP'} representative for ${mp.current_riding?.name?.en || 'constituency'}, ${mp.current_riding?.province || 'Canada'}.`}
          keywords={`${mp.name}, MP, Member of Parliament, ${mp.current_party?.name?.en || ''}, ${mp.current_riding?.name?.en || ''}, ${mp.current_riding?.province || ''}, voting record, Canadian politics`}
          ogTitle={`${mp.name} - Canadian MP`}
          ogDescription={`${mp.current_party?.name?.en || 'MP'} representative for ${mp.current_riding?.name?.en || 'constituency'}. View voting records and parliamentary activity.`}
          jsonLd={mpJsonLd}
        />
      )}
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
            src={`/api/images/${mp.url.replace('/politicians/', '').replace('/', '')}`}
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
          <p style={{ 
            margin: '5px 0', 
            fontSize: '18px', 
            color: getPartyColor(mp.current_party?.short_name?.en || mp.memberships?.[0]?.party?.short_name?.en),
            fontWeight: '600'
          }}>
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
        <style>{`
          .mp-detail-tabs {
            display: flex;
            gap: 0;
            flex-wrap: wrap;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none;
            -ms-overflow-style: none;
          }
          .mp-detail-tabs::-webkit-scrollbar {
            display: none;
          }
          .mp-detail-tab {
            padding: 12px 24px;
            border: none;
            background-color: transparent;
            cursor: pointer;
            font-size: 16px;
            font-family: inherit;
            white-space: nowrap;
            flex-shrink: 0;
            margin-bottom: -2px;
            transition: all 0.2s ease;
          }
          @media (max-width: 768px) {
            .mp-detail-tabs {
              gap: 8px;
              padding: 0 4px;
            }
            .mp-detail-tab {
              padding: 10px 16px;
              font-size: 14px;
              min-width: auto;
            }
            .mp-detail-tab.sponsored-bills {
              font-size: 13px;
              padding: 10px 12px;
            }
          }
          @media (max-width: 480px) {
            .mp-detail-tabs {
              gap: 4px;
              padding: 0 2px;
            }
            .mp-detail-tab {
              padding: 8px 12px;
              font-size: 13px;
            }
            .mp-detail-tab.sponsored-bills {
              font-size: 12px;
              padding: 8px 10px;
            }
          }
        `}</style>
        <div className="mp-detail-tabs">
          <button
            onClick={() => updateActiveTab('votes')}
            className="mp-detail-tab"
            style={{
              color: activeTab === 'votes' ? '#333' : '#666',
              fontWeight: activeTab === 'votes' ? '600' : 'normal',
              borderBottom: activeTab === 'votes' ? '2px solid #333' : '2px solid transparent'
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
            onClick={() => updateActiveTab('statistics')}
            className="mp-detail-tab"
            style={{
              color: activeTab === 'statistics' ? '#333' : '#666',
              fontWeight: activeTab === 'statistics' ? '600' : 'normal',
              borderBottom: activeTab === 'statistics' ? '2px solid #333' : '2px solid transparent'
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
          {/* Only show Bills tab if MP has sponsored bills */}
          {!billsLoading && sponsoredBills.length > 0 && (
            <button
              onClick={() => updateActiveTab('bills')}
              className="mp-detail-tab sponsored-bills"
              style={{
                color: activeTab === 'bills' ? '#333' : '#666',
                fontWeight: activeTab === 'bills' ? '600' : 'normal',
                borderBottom: activeTab === 'bills' ? '2px solid #333' : '2px solid transparent'
              }}
              onMouseEnter={(e) => {
                if (activeTab !== 'bills') {
                  e.target.style.color = '#333';
                }
              }}
              onMouseLeave={(e) => {
                if (activeTab !== 'bills') {
                  e.target.style.color = '#666';
                }
              }}
            >
              📋 Sponsored Bills ({sponsoredBills.length})
            </button>
          )}
          <button
            onClick={() => updateActiveTab('debates')}
            className="mp-detail-tab"
            style={{
              color: activeTab === 'debates' ? '#333' : '#666',
              fontWeight: activeTab === 'debates' ? '600' : 'normal',
              borderBottom: activeTab === 'debates' ? '2px solid #333' : '2px solid transparent'
            }}
            onMouseEnter={(e) => {
              if (activeTab !== 'debates') {
                e.target.style.color = '#333';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'debates') {
                e.target.style.color = '#666';
              }
            }}
          >
            🗣️ Debates
          </button>
          <button
            onClick={() => updateActiveTab('expenditures')}
            className="mp-detail-tab"
            style={{
              color: activeTab === 'expenditures' ? '#333' : '#666',
              fontWeight: activeTab === 'expenditures' ? '600' : 'normal',
              borderBottom: activeTab === 'expenditures' ? '2px solid #333' : '2px solid transparent'
            }}
            onMouseEnter={(e) => {
              if (activeTab !== 'expenditures') {
                e.target.style.color = '#333';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'expenditures') {
                e.target.style.color = '#666';
              }
            }}
          >
            💰 Expenditures
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
                      📋 <strong>Bill:</strong> {vote.bill_url.replace('/bills/', '').replace('/', ' ').replace(/\/$/, '')}
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

      {/* Bills Tab */}
      {activeTab === 'bills' && (
        <div>
          <div style={{ marginBottom: '30px' }}>
            <h2 style={{ margin: '0 0 20px 0' }}>
              Sponsored Bills
              {!billsLoading && (
                <span style={{ fontSize: '16px', fontWeight: 'normal', color: '#666', marginLeft: '10px' }}>
                  ({sponsoredBills.length})
                </span>
              )}
            </h2>

            {billsLoading && (
              <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                Loading sponsored bills...
              </div>
            )}

            {!billsLoading && sponsoredBills.length === 0 && (
              <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                <h4>No sponsored bills found</h4>
                <p>{mp.name} has not sponsored any bills in the current parliamentary session.</p>
              </div>
            )}

            {!billsLoading && sponsoredBills.length > 0 && (
              <div 
                style={{ 
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: '20px',
                  width: '100%'
                }}
                className="sponsored-bills-grid"
              >
                <style>{`
                  @media (min-width: 769px) {
                    .sponsored-bills-grid {
                      display: grid !important;
                      grid-template-columns: repeat(auto-fill, 400px) !important;
                      justify-content: start !important;
                      gap: 20px !important;
                    }
                  }
                `}</style>
                {sponsoredBills.map((bill) => (
                  <BillCard
                    key={`${bill.session}-${bill.number}`}
                    bill={bill}
                    onClick={() => navigate(`/bill/${bill.session}/${bill.number}`)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Debates Tab */}
      {activeTab === 'debates' && (
        <div>
          <div style={{ marginBottom: '30px' }}>
            <h2 style={{ margin: '0 0 20px 0' }}>
              {mp.name}'s Parliamentary Debates
            </h2>
            {debates && debates.debates_count !== undefined && (
              <p style={{ color: '#666', fontSize: '14px', marginBottom: '20px' }}>
                Participated in {debates.debates_count} debates | 
                Based on {debates.speeches_analyzed} speeches analyzed | 
                Last updated: {new Date(debates.last_updated).toLocaleDateString()}
              </p>
            )}
          </div>

          {debatesLoading && (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <div>Loading debate participation data...</div>
            </div>
          )}

          {!debatesLoading && debates && debates.debates && debates.debates.length > 0 && (
            <div>
              <div 
                style={{ 
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                  gap: '20px',
                  width: '100%'
                }}
                className="mp-debates-grid"
              >
                <style>{`
                  @media (min-width: 769px) {
                    .mp-debates-grid {
                      display: grid !important;
                      grid-template-columns: repeat(auto-fill, 400px) !important;
                      justify-content: start !important;
                      gap: 20px !important;
                    }
                  }
                `}</style>
                {debates.debates.map((debate, index) => (
                  <DebateCard
                    key={`${debate.date}-${index}`}
                    debate={debate}
                    showQuote={true}
                    mpName={mp.name}
                  />
                ))}
              </div>
              
              <div style={{ marginTop: '30px', textAlign: 'center' }}>
                <a 
                  href="https://openparliament.ca/debates/"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: '#007bff',
                    textDecoration: 'none',
                    fontWeight: '600',
                    fontSize: '14px'
                  }}
                >
                  🔗 View all parliamentary debates on OpenParliament.ca
                </a>
              </div>
            </div>
          )}

          {!debatesLoading && debates && (!debates.debates || debates.debates.length === 0) && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
              <h4>No debate participation found</h4>
              <p>{mp.name} has no recorded debate participation in our database.</p>
              <p style={{ fontSize: '14px', marginTop: '15px' }}>
                Note: Debate data is based on speeches in the House of Commons. 
                This may not include all forms of parliamentary participation.
              </p>
            </div>
          )}

          {!debatesLoading && !debates && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
              <h4>Debate data not available</h4>
              <p>Unable to retrieve debate participation information for {mp.name}.</p>
            </div>
          )}
        </div>
      )}

      {/* Expenditures Tab */}
      {activeTab === 'expenditures' && (
        <div>
          <div style={{ marginBottom: '30px' }}>
            <h2 style={{ margin: '0 0 20px 0' }}>
              {mp.name}'s Expenditures
            </h2>
            {expenditures && (
              <p style={{ color: '#666', fontSize: '14px', marginBottom: '20px' }}>
                {expenditures.historical_data ? (
                  <>
                    Historical data: {expenditures.years_covered} fiscal years, {expenditures.quarters_covered} quarters | 
                    Scraped: {new Date(expenditures.scraped_at).toLocaleDateString()}
                  </>
                ) : (
                  <>
                    Data scraped: {new Date(expenditures.scraped_at).toLocaleDateString()}
                    {expenditures.raw_response_length && (
                      <> | Response size: {expenditures.raw_response_length?.toLocaleString()} bytes</>
                    )}
                    {expenditures.expenditure_mentions && (
                      <> | Expenditure mentions: {expenditures.expenditure_mentions}</>
                    )}
                  </>
                )}
              </p>
            )}
          </div>

          {expendituresLoading && (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <div>Loading expenditure data...</div>
            </div>
          )}

          {!expendituresLoading && expenditures && expenditures.cached && (
            <div>

              {/* Quarterly Breakdown */}
              <div style={{
                backgroundColor: 'white',
                padding: '25px',
                borderRadius: '8px',
                border: '1px solid #dee2e6',
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
              }}>
                <h3 style={{ margin: '0 0 20px 0', color: '#495057' }}>Quarterly Breakdown</h3>
                
                {expenditures.periods && expenditures.periods.length > 0 ? (() => {
                  // Group periods by fiscal year for better organization
                  const periodsByFiscalYear = {};
                  expenditures.periods.forEach(period => {
                    const fiscalYear = period.fiscal_year || 'Unknown';
                    if (!periodsByFiscalYear[fiscalYear]) {
                      periodsByFiscalYear[fiscalYear] = [];
                    }
                    periodsByFiscalYear[fiscalYear].push(period);
                  });

                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '25px' }}>
                      {Object.keys(periodsByFiscalYear)
                        .sort((a, b) => b - a) // Sort by fiscal year descending
                        .map(fiscalYear => (
                          <div key={fiscalYear}>
                            <h4 style={{ 
                              margin: '0 0 15px 0', 
                              color: '#495057',
                              fontSize: '18px',
                              borderBottom: '2px solid #007bff',
                              paddingBottom: '5px'
                            }}>
                              Fiscal Year {fiscalYear - 1}-{fiscalYear}
                            </h4>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                              {periodsByFiscalYear[fiscalYear].map((period, index) => (
                                <div key={`${fiscalYear}-${index}`} style={{
                                  border: '1px solid #dee2e6',
                                  borderRadius: '5px',
                                  padding: '20px',
                                  backgroundColor: '#f8f9fa'
                                }}>
                                  <h5 style={{ 
                                    margin: '0 0 15px 0', 
                                    color: '#495057',
                                    fontSize: '16px'
                                  }}>
                                    {period.period_description || period.period?.split('\n')[0] || `Q${period.quarter || index + 1}`}
                                  </h5>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px' }}>
                          <div>
                            <span style={{ fontSize: '14px', color: '#666' }}>💼 Salaries: </span>
                            <span style={{ fontWeight: '600' }}>{period.salaries_formatted || '$0'}</span>
                          </div>
                          <div>
                            <span style={{ fontSize: '14px', color: '#666' }}>✈️ Travel: </span>
                            <span style={{ fontWeight: '600' }}>{period.travel_formatted || '$0'}</span>
                          </div>
                          <div>
                            <span style={{ fontSize: '14px', color: '#666' }}>🍽️ Hospitality: </span>
                            <span style={{ fontWeight: '600' }}>{period.hospitality_formatted || '$0'}</span>
                          </div>
                          <div>
                            <span style={{ fontSize: '14px', color: '#666' }}>📋 Contracts: </span>
                            <span style={{ fontWeight: '600' }}>{period.contracts_formatted || '$0'}</span>
                          </div>
                        </div>
                        
                        <div style={{ marginTop: '10px', textAlign: 'right' }}>
                          <span style={{ fontSize: '16px', fontWeight: 'bold', color: '#007bff' }}>
                            Quarter Total: ${(
                              (period.salaries_amount || 0) + 
                              (period.travel_amount || 0) + 
                              (period.hospitality_amount || 0) + 
                              (period.contracts_amount || 0)
                            ).toLocaleString()}
                          </span>
                                </div>
                              </div>
                              ))}
                            </div>
                          </div>
                        ))}
                    </div>
                  );
                })() : (
                  <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
                    <p>No quarterly expenditure data available.</p>
                  </div>
                )}
                
                <div style={{ marginTop: '20px', textAlign: 'center' }}>
                  <a 
                    href="https://www.ourcommons.ca/ProactiveDisclosure/en/members"
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      color: '#007bff',
                      textDecoration: 'none',
                      fontWeight: '600',
                      fontSize: '14px'
                    }}
                  >
                    🔗 View detailed reports on House of Commons website
                  </a>
                </div>
              </div>
            </div>
          )}

          {!expendituresLoading && expenditures && !expenditures.cached && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
              <h4>Expenditure data not available</h4>
              <p>{expenditures.message || 'Expenditure data may still be collecting or not available for this MP.'}</p>
            </div>
          )}

          {!expendituresLoading && !expenditures && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
              <h4>No expenditure data found</h4>
              <p>Unable to retrieve expenditure information for {mp.name}.</p>
            </div>
          )}
        </div>
      )}
      </div>
    </>
  );
}

export default MPDetail;