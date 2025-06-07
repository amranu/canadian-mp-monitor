import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { parliamentApi } from '../services/parliamentApi';

function BillDetail() {
  const { session, number } = useParams();
  const navigate = useNavigate();
  const [bill, setBill] = useState(null);
  const [loading, setLoading] = useState(true);
  const [relatedVotes, setRelatedVotes] = useState([]);
  const [loadingVotes, setLoadingVotes] = useState(false);

  useEffect(() => {
    loadBill();
    loadRelatedVotes();
  }, [session, number]);

  const loadBill = async () => {
    try {
      setLoading(true);
      const data = await parliamentApi.getBill(session, number);
      setBill(data);
    } catch (error) {
      console.error('Error loading bill:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadRelatedVotes = async () => {
    try {
      setLoadingVotes(true);
      
      const billUrl = `/bills/${session}/${number}/`;
      let allRelatedVotes = [];
      let offset = 0;
      const limit = 200;
      let hasMoreVotes = true;
      
      // Search through multiple pages of votes to find all related ones
      while (hasMoreVotes && offset < 2000) { // Limit search to prevent infinite loops
        try {
          const votesData = await parliamentApi.getVotes(limit, offset);
          
          if (!votesData.objects || votesData.objects.length === 0) {
            hasMoreVotes = false;
            break;
          }
          
          // Filter for votes related to this bill
          const related = votesData.objects.filter(vote => vote.bill_url === billUrl);
          allRelatedVotes.push(...related);
          
          // If we found related votes, continue searching (bills can have multiple votes)
          // Otherwise, if no related votes in this batch and we've searched enough, stop
          if (related.length === 0 && offset > 600) {
            // If no matches in recent votes and we've searched far enough, stop
            hasMoreVotes = false;
          } else {
            offset += limit;
            // Check if there are more votes to fetch
            hasMoreVotes = votesData.objects.length === limit;
          }
          
          // Small delay to avoid overwhelming the API
          if (hasMoreVotes) {
            await new Promise(resolve => setTimeout(resolve, 100));
          }
          
        } catch (error) {
          console.error('Error loading votes batch:', error);
          hasMoreVotes = false;
        }
      }
      
      // Sort related votes by date (most recent first)
      allRelatedVotes.sort((a, b) => new Date(b.date) - new Date(a.date));
      
      setRelatedVotes(allRelatedVotes);
      console.log(`Found ${allRelatedVotes.length} related votes for bill ${billUrl}`);
      
    } catch (error) {
      console.error('Error loading related votes:', error);
    } finally {
      setLoadingVotes(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString('en-CA', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  const getBillTypeColor = (number) => {
    if (number.startsWith('C-')) return '#007bff'; // Government bills - blue
    if (number.startsWith('S-')) return '#6f42c1'; // Senate bills - purple  
    if (number.startsWith('M-')) return '#28a745'; // Private member motions - green
    return '#6c757d'; // Other - gray
  };

  const getBillTypeLabel = (number) => {
    if (number.startsWith('C-')) return 'Government Bill';
    if (number.startsWith('S-')) return 'Senate Bill';
    if (number.startsWith('M-')) return 'Private Member Motion';
    return 'Other';
  };

  const getBillTypeDescription = (number) => {
    if (number.startsWith('C-')) return 'Bills introduced by the government in the House of Commons';
    if (number.startsWith('S-')) return 'Bills introduced in the Senate';
    if (number.startsWith('M-')) return 'Motions introduced by private members';
    return 'Other parliamentary business';
  };

  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        Loading bill details...
      </div>
    );
  }

  if (!bill) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <h2>Bill Not Found</h2>
        <p>The requested bill could not be found.</p>
        <button 
          onClick={() => navigate('/bills')}
          style={{ 
            padding: '10px 20px', 
            backgroundColor: '#007bff', 
            color: 'white', 
            border: 'none', 
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          ← Back to Bills
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px' }}>
      <button 
        onClick={() => navigate('/bills')}
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
        ← Back to Bills
      </button>

      {/* Bill Header */}
      <div style={{
        backgroundColor: 'white',
        padding: '30px',
        borderRadius: '8px',
        border: '1px solid #ddd',
        marginBottom: '30px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '20px', marginBottom: '20px' }}>
          <div style={{
            padding: '8px 16px',
            backgroundColor: getBillTypeColor(bill.number),
            color: 'white',
            borderRadius: '6px',
            fontSize: '14px',
            fontWeight: 'bold',
            whiteSpace: 'nowrap'
          }}>
            {getBillTypeLabel(bill.number)}
          </div>
          
          <div style={{ flex: 1 }}>
            <h1 style={{ margin: '0 0 10px 0', fontSize: '28px', lineHeight: '1.3' }}>
              {bill.name?.en || 'Bill name not available'}
            </h1>
            
            {bill.name?.fr && bill.name.fr !== bill.name?.en && (
              <h2 style={{ 
                margin: '0 0 15px 0', 
                fontSize: '22px', 
                fontWeight: '400',
                color: '#666',
                fontStyle: 'italic',
                lineHeight: '1.3'
              }}>
                {bill.name.fr}
              </h2>
            )}
          </div>

          <div style={{
            padding: '15px',
            backgroundColor: '#f8f9fa',
            borderRadius: '6px',
            textAlign: 'center',
            minWidth: '120px'
          }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#495057' }}>
              {session} - {number}
            </div>
            <div style={{ fontSize: '12px', color: '#6c757d', marginTop: '5px' }}>
              Bill Number
            </div>
          </div>
        </div>

        {/* Bill Info Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '20px',
          marginTop: '20px',
          padding: '20px',
          backgroundColor: '#f8f9fa',
          borderRadius: '6px'
        }}>
          <div>
            <h4 style={{ margin: '0 0 8px 0', color: '#495057' }}>Session</h4>
            <p style={{ margin: '0', fontSize: '16px', fontWeight: '500' }}>{bill.session}</p>
          </div>
          
          <div>
            <h4 style={{ margin: '0 0 8px 0', color: '#495057' }}>Introduced</h4>
            <p style={{ margin: '0', fontSize: '16px', fontWeight: '500' }}>{formatDate(bill.introduced)}</p>
          </div>
          
          <div>
            <h4 style={{ margin: '0 0 8px 0', color: '#495057' }}>Bill Type</h4>
            <p style={{ margin: '0', fontSize: '16px', fontWeight: '500' }}>{getBillTypeLabel(bill.number)}</p>
            <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#6c757d' }}>
              {getBillTypeDescription(bill.number)}
            </p>
          </div>

          {bill.legisinfo_id && (
            <div>
              <h4 style={{ margin: '0 0 8px 0', color: '#495057' }}>LEGISinfo ID</h4>
              <p style={{ margin: '0', fontSize: '16px', fontWeight: '500' }}>{bill.legisinfo_id}</p>
            </div>
          )}
        </div>
      </div>

      {/* Related Votes Section */}
      <div style={{
        backgroundColor: 'white',
        padding: '25px',
        borderRadius: '8px',
        border: '1px solid #ddd',
        boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
      }}>
        <h2 style={{ margin: '0 0 20px 0', color: '#495057' }}>
          Related Votes
          {!loadingVotes && (
            <span style={{ fontSize: '16px', fontWeight: 'normal', color: '#6c757d', marginLeft: '10px' }}>
              ({relatedVotes.length})
            </span>
          )}
        </h2>

        {loadingVotes && (
          <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
            Loading related votes...
          </div>
        )}

        {!loadingVotes && relatedVotes.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
            <h4>No votes found</h4>
            <p>No parliamentary votes have been recorded for this bill yet.</p>
          </div>
        )}

        {!loadingVotes && relatedVotes.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            {relatedVotes.map((vote) => (
              <div
                key={vote.url}
                onClick={() => {
                  // Extract vote ID from URL like "/votes/45-1/4/" -> "45-1/4"
                  const voteId = vote.url.replace('/votes/', '').replace(/\/$/, '');
                  const encodedVoteId = encodeURIComponent(voteId);
                  navigate(`/vote/${encodedVoteId}`);
                }}
                style={{
                  border: '1px solid #ddd',
                  borderRadius: '6px',
                  padding: '20px',
                  backgroundColor: '#f8f9fa',
                  cursor: 'pointer',
                  transition: 'box-shadow 0.2s, transform 0.1s'
                }}
                onMouseEnter={(e) => {
                  e.target.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
                  e.target.style.transform = 'translateY(-1px)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.boxShadow = 'none';
                  e.target.style.transform = 'translateY(0)';
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <h4 style={{ margin: '0', fontSize: '16px', color: '#333', lineHeight: '1.4' }}>
                    {vote.description?.en || 'Vote description not available'}
                  </h4>
                  
                  <div style={{
                    padding: '4px 8px',
                    borderRadius: '4px',
                    backgroundColor: vote.result === 'Passed' ? '#d4edda' : '#f8d7da',
                    color: vote.result === 'Passed' ? '#155724' : '#721c24',
                    fontWeight: 'bold',
                    fontSize: '12px',
                    marginLeft: '15px',
                    whiteSpace: 'nowrap'
                  }}>
                    {vote.result}
                  </div>
                </div>

                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '14px',
                  color: '#666'
                }}>
                  <span>
                    <strong>Date:</strong> {formatDate(vote.date)} • <strong>Vote #{vote.number}</strong>
                  </span>
                  
                  <div style={{
                    display: 'flex',
                    gap: '12px',
                    fontSize: '13px',
                    backgroundColor: 'white',
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
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default BillDetail;