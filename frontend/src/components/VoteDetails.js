import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { parliamentApi } from '../services/parliamentApi';

function VoteDetails() {
  const { voteId } = useParams();
  const navigate = useNavigate();
  const [vote, setVote] = useState(null);
  const [voteDetails, setVoteDetails] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    console.log('VoteDetails useEffect triggered, voteId:', voteId);
    if (voteId) {
      loadVoteDetails();
    }
  }, [voteId]);

  const loadVoteDetails = async () => {
    try {
      setLoading(true);
      // Decode the URL-encoded vote ID
      const decodedVoteId = decodeURIComponent(voteId);
      const voteUrl = `/votes/${decodedVoteId}/`;
      console.log('Loading vote details for voteId:', voteId, 'decoded:', decodedVoteId);
      console.log('Full vote URL:', voteUrl);
      const data = await parliamentApi.getVoteDetails(voteUrl);
      console.log('Vote details response:', data);
      setVoteDetails(data);
      // Create a vote object for the header display using the vote details data
      const voteData = data.vote || data; // Handle both nested and direct response formats
      setVote({
        url: voteUrl,
        description: voteData.description || { en: 'Parliamentary Vote' },
        date: voteData.date,
        session: voteData.session,
        number: voteData.number,
        result: voteData.result,
        bill_url: voteData.bill_url
      });
      console.log('Vote state set successfully');
    } catch (error) {
      console.error('Error loading vote details:', error);
      console.error('Vote ID:', voteId);
      // Set an error state for better user feedback
      setVoteDetails({ error: error.message });
    } finally {
      setLoading(false);
      console.log('Loading finished');
    }
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

  const getVoteColor = (ballot) => {
    switch (ballot.toLowerCase()) {
      case 'yes': return '#16a34a';
      case 'no': return '#dc2626';
      case 'paired': return '#ca8a04';
      case 'absent': return '#9ca3af';
      default: return '#6b7280';
    }
  };

  if (loading || !vote) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        Loading vote details...
      </div>
    );
  }

  if (!voteDetails) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        Error loading vote details.
      </div>
    );
  }

  if (voteDetails.error) {
    return (
      <div style={{ padding: '20px' }}>
        <button 
          onClick={() => navigate(-1)}
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
          ← Back
        </button>
        
        <div style={{ 
          backgroundColor: '#f8d7da',
          color: '#721c24',
          padding: '20px',
          borderRadius: '8px',
          border: '1px solid #f5c6cb'
        }}>
          <h3>Error Loading Vote Details</h3>
          <p><strong>Error:</strong> {voteDetails.error}</p>
          <p><strong>Vote URL:</strong> {vote.url}</p>
          <p style={{ fontSize: '14px', marginTop: '10px' }}>
            This might be due to API limitations or network issues. Please try again later.
          </p>
          <button 
            onClick={loadVoteDetails}
            style={{ 
              marginTop: '10px',
              padding: '8px 16px', 
              backgroundColor: '#007bff', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Retry Loading
          </button>
        </div>
      </div>
    );
  }

  const sortedParties = Object.entries(voteDetails.party_stats).sort((a, b) => b[1].total - a[1].total);

  return (
    <div style={{ padding: '20px' }}>
      <button 
        onClick={() => navigate(-1)}
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
        ← Back
      </button>

      {/* Vote Header */}
      <div style={{ 
        backgroundColor: '#f8f9fa',
        padding: '20px',
        borderRadius: '8px',
        marginBottom: '30px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '15px' }}>
          <div style={{ flex: 1 }}>
            {vote.bill_url && (
              <div style={{ 
                marginBottom: '15px',
                padding: '12px 16px',
                backgroundColor: '#e7f3ff',
                borderRadius: '8px',
                border: '2px solid #0969da'
              }}>
                <div style={{ fontSize: '14px', color: '#0969da', fontWeight: '600', marginBottom: '4px' }}>
                  📋 BILL
                </div>
                <div style={{ 
                  fontSize: '20px', 
                  fontWeight: 'bold', 
                  color: '#0969da',
                  lineHeight: '1.2',
                  marginBottom: '8px'
                }}>
                  {vote.bill_url.replace('/bills/', '').replace('/', ' ').toUpperCase()}
                </div>
                {(() => {
                  // Extract bill title from description
                  const description = vote.description?.en || '';
                  // Try multiple patterns to extract bill title
                  let billTitle = null;
                  
                  // Pattern 1: "Bill C-79, An Act for..."
                  let match = description.match(/Bill [A-Z]-\d+,?\s*(.+?)(?:\s*\(|$)/i);
                  if (match && match[1]) {
                    billTitle = match[1].trim();
                  }
                  
                  // Pattern 2: "...of Bill C-79, An Act for..." (for 3rd reading cases)
                  if (!billTitle) {
                    match = description.match(/of Bill [A-Z]-\d+,?\s*(.+?)(?:\s*\(|$)/i);
                    if (match && match[1]) {
                      billTitle = match[1].trim();
                    }
                  }
                  
                  if (billTitle) {
                    return (
                      <div style={{ 
                        fontSize: '16px', 
                        color: '#0969da',
                        lineHeight: '1.3',
                        fontStyle: 'italic'
                      }}>
                        {billTitle}
                      </div>
                    );
                  }
                  return null;
                })()}
              </div>
            )}
            <h1 style={{ margin: '0 0 10px 0', fontSize: '24px', lineHeight: '1.3' }}>
              {vote.description?.en}
            </h1>
            <div style={{ fontSize: '14px', color: '#666', display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
              <span><strong>📅</strong> {vote.date}</span>
              <span><strong>Session:</strong> {vote.session}</span>
              <span><strong>Vote #{vote.number}</strong></span>
            </div>
          </div>
          
          <div style={{ 
            padding: '8px 16px', 
            borderRadius: '6px',
            backgroundColor: vote.result === 'Passed' ? '#d4edda' : '#f8d7da',
            color: vote.result === 'Passed' ? '#155724' : '#721c24',
            fontWeight: 'bold',
            fontSize: '16px'
          }}>
            {vote.result}
          </div>
        </div>

      </div>


      {/* Historical MP Data Notice */}
      {voteDetails.mp_sources && voteDetails.mp_sources.historical_mps > 0 && (
        <div style={{ 
          marginBottom: '20px',
          padding: '12px 16px',
          backgroundColor: '#fff3cd',
          borderRadius: '6px',
          border: '1px solid #ffeaa7'
        }}>
          <div style={{ fontSize: '14px', color: '#856404', fontWeight: '600', marginBottom: '4px' }}>
            📚 Historical Parliament Data
          </div>
          <div style={{ fontSize: '14px', color: '#856404' }}>
            This vote includes {voteDetails.mp_sources.historical_mps} MPs from a previous parliamentary session who are no longer in office.
            {voteDetails.mp_sources.current_mps > 0 && ` Also showing ${voteDetails.mp_sources.current_mps} current MPs.`}
          </div>
        </div>
      )}

      {/* Party Statistics */}
      <div style={{ marginBottom: '30px' }}>
        <h2 style={{ marginBottom: '20px' }}>Party Voting Statistics</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px' }}>
          {sortedParties.map(([party, stats]) => (
            <div key={party} style={{
              border: '1px solid #ddd',
              borderRadius: '8px',
              padding: '15px',
              backgroundColor: 'white'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                <div style={{
                  width: '12px',
                  height: '12px',
                  backgroundColor: getPartyColor(party),
                  borderRadius: '2px',
                  marginRight: '8px'
                }}></div>
                <h3 style={{ margin: 0, fontSize: '16px' }}>{party}</h3>
              </div>
              
              <div style={{ fontSize: '14px', lineHeight: '1.5' }}>
                <div><strong>Total MPs:</strong> {stats.total}</div>
                <div style={{ color: '#16a34a' }}><strong>✓ Yes:</strong> {stats.yes} ({Math.round(stats.yes / stats.total * 100)}%)</div>
                <div style={{ color: '#dc2626' }}><strong>✗ No:</strong> {stats.no} ({Math.round(stats.no / stats.total * 100)}%)</div>
                {stats.paired > 0 && <div style={{ color: '#ca8a04' }}><strong>⚖️ Paired:</strong> {stats.paired}</div>}
                {stats.absent > 0 && <div style={{ color: '#9ca3af' }}><strong>📭 Absent:</strong> {stats.absent}</div>}
                {stats.other > 0 && <div style={{ color: '#6b7280' }}><strong>Other:</strong> {stats.other}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Unified MP Vote Visualization */}
      <div style={{ marginBottom: '30px' }}>
        <h2 style={{ marginBottom: '20px' }}>Individual MP Votes</h2>
        <p style={{ color: '#666', marginBottom: '20px', fontSize: '14px' }}>
          Each square represents an MP. Square color = party, border color = vote. Hover for details.
        </p>
        
        {/* All MP Squares in One Grid */}
        <div style={{
          padding: '20px',
          backgroundColor: '#f8f9fa',
          borderRadius: '8px',
          border: '1px solid #ddd',
          marginBottom: '20px'
        }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, 24px)',
            gap: '3px',
            justifyContent: 'start'
          }}>
            {voteDetails.ballots
              .sort((a, b) => {
                // Sort by party first, then by vote type, then by name
                if (a.mp_party !== b.mp_party) {
                  return a.mp_party.localeCompare(b.mp_party);
                }
                const voteOrder = { 'Yes': 0, 'No': 1, 'Paired': 2, 'Absent': 3 };
                const aOrder = voteOrder[a.ballot] || 9;
                const bOrder = voteOrder[b.ballot] || 9;
                if (aOrder !== bOrder) return aOrder - bOrder;
                return a.mp_name.localeCompare(b.mp_name);
              })
              .map((mp, index) => (
                <div
                  key={index}
                  title={`${mp.mp_name} (${mp.mp_party})\n${mp.mp_riding}, ${mp.mp_province}\nVoted: ${mp.ballot}`}
                  style={{
                    width: '22px',
                    height: '22px',
                    backgroundColor: getPartyColor(mp.mp_party),
                    border: `3px solid ${getVoteColor(mp.ballot)}`,
                    borderRadius: '3px',
                    cursor: 'pointer',
                    opacity: mp.ballot.toLowerCase() === 'absent' ? 0.4 : 1,
                    transition: 'transform 0.1s, box-shadow 0.1s'
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.transform = 'scale(1.3)';
                    e.target.style.boxShadow = '0 3px 12px rgba(0,0,0,0.4)';
                    e.target.style.zIndex = '10';
                    e.target.style.position = 'relative';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.transform = 'scale(1)';
                    e.target.style.boxShadow = 'none';
                    e.target.style.zIndex = 'auto';
                    e.target.style.position = 'static';
                  }}
                />
              ))}
          </div>
        </div>
        
        {/* Color Legend */}
        <div style={{ marginBottom: '20px', fontSize: '12px', color: '#666' }}>
          <div style={{ display: 'flex', gap: '25px', flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <strong>Square Colors (Parties):</strong>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#1e3a8a', borderRadius: '2px' }}></div>
                <span>Conservative</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#dc2626', borderRadius: '2px' }}></div>
                <span>Liberal</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#ea580c', borderRadius: '2px' }}></div>
                <span>NDP</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#06b6d4', borderRadius: '2px' }}></div>
                <span>Bloc</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#16a34a', borderRadius: '2px' }}></div>
                <span>Green</span>
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '25px', flexWrap: 'wrap', alignItems: 'center', marginTop: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              <strong>Border Colors (Votes):</strong>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', border: '2px solid #16a34a', borderRadius: '2px', backgroundColor: '#f0f0f0' }}></div>
                <span>Yes</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', border: '2px solid #dc2626', borderRadius: '2px', backgroundColor: '#f0f0f0' }}></div>
                <span>No</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', border: '2px solid #ca8a04', borderRadius: '2px', backgroundColor: '#f0f0f0' }}></div>
                <span>Paired</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', border: '2px solid #9ca3af', borderRadius: '2px', backgroundColor: '#f0f0f0', opacity: 0.4 }}></div>
                <span>Absent</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Detailed MP List */}
      <div>
        <h2 style={{ marginBottom: '20px' }}>Detailed MP Voting List</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {voteDetails.ballots
            .sort((a, b) => a.mp_name.localeCompare(b.mp_name))
            .map((ballot, index) => (
            <div key={index} style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '10px 15px',
              backgroundColor: index % 2 === 0 ? '#f8f9fa' : 'white',
              borderRadius: '4px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{
                  width: '12px',
                  height: '12px',
                  backgroundColor: getPartyColor(ballot.mp_party),
                  borderRadius: '2px'
                }}></div>
                <span style={{ fontWeight: '500' }}>{ballot.mp_name}</span>
                <span style={{ color: '#666', fontSize: '14px' }}>
                  ({ballot.mp_party}) - {ballot.mp_riding}, {ballot.mp_province}
                </span>
              </div>
              
              <div style={{
                padding: '4px 8px',
                borderRadius: '4px',
                backgroundColor: getVoteColor(ballot.ballot),
                color: 'white',
                fontSize: '12px',
                fontWeight: 'bold'
              }}>
                {ballot.ballot}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default VoteDetails;