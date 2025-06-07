import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { parliamentApi } from '../services/parliamentApi';

function Bills() {
  const navigate = useNavigate();
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [sessionFilter, setSessionFilter] = useState('');
  const [availableSessions, setAvailableSessions] = useState([]);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    loadBills();
  }, [sessionFilter]);

  const loadBills = async (resetOffset = true) => {
    try {
      setLoading(true);
      const newOffset = resetOffset ? 0 : offset;
      
      const filters = {};
      if (sessionFilter) {
        filters.session = sessionFilter;
      }

      const data = await parliamentApi.getBills(50, newOffset, filters);
      
      if (resetOffset) {
        setBills(data.objects);
        setOffset(50);
        
        // Extract available sessions
        const allData = await parliamentApi.getBills(1000, 0);
        const sessions = [...new Set(allData.objects.map(bill => bill.session))].sort().reverse();
        setAvailableSessions(sessions);
      } else {
        setBills(prevBills => [...prevBills, ...data.objects]);
        setOffset(prevOffset => prevOffset + 50);
      }
      
      setTotalCount(data.total_count || data.objects.length);
      setHasMore(data.objects.length === 50); // If we got a full page, there might be more
      
    } catch (error) {
      console.error('Error loading bills:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMoreBills = () => {
    if (!loading && hasMore) {
      loadBills(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadBills();
      return;
    }

    try {
      setLoading(true);
      const filters = {};
      if (sessionFilter) {
        filters.session = sessionFilter;
      }
      
      const data = await parliamentApi.searchBills(searchQuery, filters);
      setBills(data.objects);
      setTotalCount(data.total_count);
      setHasMore(false); // Search results are not paginated
      setOffset(0);
    } catch (error) {
      console.error('Error searching bills:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const clearSearch = () => {
    setSearchQuery('');
    loadBills();
  };

  const formatBillNumber = (bill) => {
    return `${bill.session} - ${bill.number}`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString('en-CA');
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
    if (number.startsWith('M-')) return 'Private Motion';
    return 'Other';
  };

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '30px' }}>
        <h1 style={{ margin: '0 0 10px 0' }}>Parliamentary Bills</h1>
        <p style={{ color: '#666', marginBottom: '20px' }}>
          Browse and search bills introduced in the Canadian Parliament
        </p>

        {/* Search and Filter Controls */}
        <div style={{ 
          display: 'flex', 
          gap: '15px', 
          marginBottom: '20px',
          flexWrap: 'wrap',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', gap: '10px', flex: '1', minWidth: '300px' }}>
            <input
              type="text"
              placeholder="Search bills by name or number..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              style={{
                flex: '1',
                padding: '10px 15px',
                border: '1px solid #ddd',
                borderRadius: '6px',
                fontSize: '16px',
                outline: 'none'
              }}
            />
            <button
              onClick={handleSearch}
              style={{
                padding: '10px 20px',
                backgroundColor: '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '16px'
              }}
            >
              Search
            </button>
            {searchQuery && (
              <button
                onClick={clearSearch}
                style={{
                  padding: '10px 15px',
                  backgroundColor: '#6c757d',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '16px'
                }}
              >
                Clear
              </button>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <label style={{ fontSize: '14px', color: '#666', fontWeight: '500' }}>
              Session:
            </label>
            <select
              value={sessionFilter}
              onChange={(e) => setSessionFilter(e.target.value)}
              style={{
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: 'white',
                fontSize: '14px',
                cursor: 'pointer'
              }}
            >
              <option value="">All Sessions</option>
              {availableSessions.map(session => (
                <option key={session} value={session}>
                  {session}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Results Summary */}
        <div style={{ 
          fontSize: '14px', 
          color: '#666', 
          marginBottom: '20px' 
        }}>
          {searchQuery ? (
            <>Showing {bills.length} search results for "{searchQuery}"</>
          ) : (
            <>Showing {bills.length} of {totalCount} bills{sessionFilter && ` from session ${sessionFilter}`}</>
          )}
        </div>
      </div>

      {/* Bills Grid */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', 
        gap: '20px',
        marginBottom: '30px'
      }}>
        {bills.map((bill) => (
          <div
            key={`${bill.session}-${bill.number}`}
            onClick={() => navigate(`/bill/${bill.session}/${bill.number}`)}
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
                <div style={{
                  padding: '4px 8px',
                  backgroundColor: getBillTypeColor(bill.number),
                  color: 'white',
                  borderRadius: '4px',
                  fontSize: '12px',
                  fontWeight: 'bold'
                }}>
                  {getBillTypeLabel(bill.number)}
                </div>
                <div style={{
                  fontSize: '14px',
                  color: '#666',
                  fontWeight: 'bold'
                }}>
                  {formatBillNumber(bill)}
                </div>
              </div>

              <h3 style={{
                margin: '0 0 10px 0',
                fontSize: '18px',
                lineHeight: '1.4',
                color: '#333',
                fontWeight: '600'
              }}>
                {bill.name?.en || 'Bill name not available'}
              </h3>

              {bill.name?.fr && bill.name.fr !== bill.name?.en && (
                <p style={{
                  margin: '0 0 10px 0',
                  fontSize: '14px',
                  color: '#666',
                  fontStyle: 'italic',
                  lineHeight: '1.3'
                }}>
                  {bill.name.fr}
                </p>
              )}
            </div>

            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '14px',
              color: '#666'
            }}>
              <span>
                <strong>Introduced:</strong> {formatDate(bill.introduced)}
              </span>
              <span>
                <strong>Session:</strong> {bill.session}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Loading State */}
      {loading && bills.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
          Loading bills...
        </div>
      )}

      {/* No Results */}
      {!loading && bills.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
          {searchQuery ? (
            <>
              <h3>No bills found</h3>
              <p>No bills match your search criteria. Try adjusting your search terms or filters.</p>
            </>
          ) : (
            <>
              <h3>No bills available</h3>
              <p>No bills are currently available in the selected session.</p>
            </>
          )}
        </div>
      )}

      {/* Load More Button */}
      {hasMore && !searchQuery && bills.length > 0 && (
        <div style={{ textAlign: 'center', marginTop: '30px' }}>
          <button
            onClick={loadMoreBills}
            disabled={loading}
            style={{
              padding: '12px 24px',
              backgroundColor: loading ? '#6c757d' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontSize: '16px',
              fontWeight: '500',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'background-color 0.2s'
            }}
          >
            {loading ? 'Loading...' : 'Load More Bills'}
          </button>
        </div>
      )}
    </div>
  );
}

export default Bills;