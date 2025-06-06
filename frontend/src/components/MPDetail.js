import React, { useState, useEffect } from 'react';
import { parliamentApi } from '../services/parliamentApi';
import VoteDetails from './VoteDetails';

function MPDetail({ mp, onBack }) {
  const [mpDetails, setMpDetails] = useState(null);
  const [votes, setVotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedVote, setSelectedVote] = useState(null);

  useEffect(() => {
    loadMPDetails();
    loadRecentVotes();
  }, [mp]);

  const loadMPDetails = async () => {
    try {
      const data = await parliamentApi.getMP(mp.url);
      setMpDetails(data);
    } catch (error) {
      console.error('Error loading MP details:', error);
    }
  };

  const loadRecentVotes = async (retryCount = 0) => {
    try {
      const data = await parliamentApi.getMPVotes(mp.url, 20);
      
      // Check if votes are being loaded in background
      if (data.loading && retryCount < 3) {
        console.log(`Votes loading in background, retrying in 3 seconds... (attempt ${retryCount + 1}/3)`);
        setTimeout(() => {
          loadRecentVotes(retryCount + 1);
        }, 3000);
        return;
      }
      
      if (data.objects && data.objects.length > 0) {
        setVotes(data.objects);
        if (data.cached) {
          console.log('Serving cached MP votes');
        }
      } else if (retryCount >= 3) {
        // After 3 retries, fallback to general votes
        console.log('Falling back to general parliamentary votes');
        const fallbackData = await parliamentApi.getVotes(20);
        setVotes(fallbackData.objects);
      }
    } catch (error) {
      console.error('Error loading MP votes:', error);
      // Fallback to general votes if individual votes fail
      try {
        const fallbackData = await parliamentApi.getVotes(20);
        setVotes(fallbackData.objects);
      } catch (fallbackError) {
        console.error('Error loading fallback votes:', fallbackError);
      }
    } finally {
      if (retryCount === 0 || retryCount >= 3) {
        setLoading(false);
      }
    }
  };

  if (selectedVote) {
    return (
      <VoteDetails 
        vote={selectedVote} 
        onBack={() => setSelectedVote(null)} 
      />
    );
  }

  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        Loading MP details...
      </div>
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <button 
        onClick={onBack}
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
            {mp.current_party?.short_name?.en}
          </p>
          <p style={{ margin: '5px 0', fontSize: '16px', color: '#666' }}>
            {mp.current_riding?.name?.en}, {mp.current_riding?.province}
          </p>
          {mpDetails?.email && (
            <p style={{ margin: '5px 0', fontSize: '14px' }}>
              Email: <a href={`mailto:${mpDetails.email}`}>{mpDetails.email}</a>
            </p>
          )}
        </div>
      </div>

      <div>
        <h2>{mp.name}'s Recent Voting Record</h2>
        <p style={{ color: '#666', marginBottom: '20px' }}>
          Showing how {mp.name} voted on recent parliamentary matters.
          {votes.length > 0 && (
            <span style={{ color: '#0969da' }}> Click any vote to see detailed party statistics and all MP votes.</span>
          )}
          {votes.length === 0 && !loading && (
            <span style={{ color: '#856404' }}> Individual voting records are being cached in the background.</span>
          )}
        </p>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {votes.map((vote) => {
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
                onClick={() => setSelectedVote(vote)}
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
                      
                      {vote.mp_ballot && (
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
                      )}
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
      </div>
    </div>
  );
}

export default MPDetail;