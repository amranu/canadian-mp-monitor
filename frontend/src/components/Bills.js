import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { parliamentApi } from '../services/parliamentApi';
import BillCard from './BillCard';

function Bills() {
  const navigate = useNavigate();
  const [bills, setBills] = useState([]);
  const [allBills, setAllBills] = useState([]); // Store all bills for client-side filtering
  
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState(''); // Input field value
  const [activeSearch, setActiveSearch] = useState(''); // Currently applied search
  const [sessionFilter, setSessionFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [hasVotesFilter, setHasVotesFilter] = useState(false);
  const [availableSessions, setAvailableSessions] = useState([]);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [filterLoading, setFilterLoading] = useState(false);

  useEffect(() => {
    loadBills();
  }, [sessionFilter, typeFilter, hasVotesFilter]);

  // Button-based search filtering
  useEffect(() => {
    if (!allBills.length) return;
    
    let filteredBills = allBills;
    
    // Apply search query filter only when activeSearch is set
    if (activeSearch.trim()) {
      const query = activeSearch.toLowerCase();
      filteredBills = filteredBills.filter(bill => 
        bill.name?.en?.toLowerCase().includes(query) ||
        bill.name?.fr?.toLowerCase().includes(query) ||
        bill.number?.toLowerCase().includes(query)
      );
    }
    
    setBills(filteredBills);
    setTotalCount(filteredBills.length);
    setHasMore(false); // Disable pagination for filtered results
  }, [activeSearch, allBills]);

  const loadBills = async (resetOffset = true) => {
    try {
      setLoading(true);
      if (resetOffset) {
        setFilterLoading(true);
      }
      
      const filters = {};
      if (sessionFilter) {
        filters.session = sessionFilter;
      }
      if (typeFilter) {
        filters.type = typeFilter;
      }
      if (hasVotesFilter) {
        filters.has_votes = 'true';
      }

      // Load all bills for the current filters to enable real-time search
      const data = await parliamentApi.getBills(10000, 0, filters); // Large limit to get all
      
      setAllBills(data.objects);
      // Don't set bills here - let the search useEffect handle it based on searchQuery
      setTotalCount(data.total_count || data.objects.length);
      setHasMore(false); // Disable pagination since we load all bills
      setOffset(0);
      
      // Extract available sessions (only do this once on initial load)
      if (!availableSessions.length) {
        const allData = await parliamentApi.getBills(1000, 0);
        const sessions = [...new Set(allData.objects.map(bill => bill.session))].sort().reverse();
        setAvailableSessions(sessions);
      }
      
    } catch (error) {
      console.error('Error loading bills:', error);
    } finally {
      setLoading(false);
      setFilterLoading(false);
    }
  };

  const loadMoreBills = () => {
    if (!loading && hasMore) {
      loadBills(false);
    }
  };

  const handleSearch = () => {
    setActiveSearch(searchInput);
    setSearchQuery(searchInput); // Keep for display purposes
  };

  const clearSearch = () => {
    setSearchInput('');
    setActiveSearch('');
    setSearchQuery('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };


  return (
    <div style={{ padding: '12px' }}>
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
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
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
              disabled={!searchInput.trim()}
              style={{
                padding: '10px 20px',
                backgroundColor: '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '16px',
                fontWeight: '500',
                opacity: searchInput.trim() ? 1 : 0.5
              }}
            >
              Search
            </button>
            {activeSearch && (
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

          <div style={{ display: 'flex', alignItems: 'center', gap: '15px', flexWrap: 'wrap' }}>
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

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <label style={{ fontSize: '14px', color: '#666', fontWeight: '500' }}>
                Type:
              </label>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                style={{
                  padding: '8px 12px',
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  backgroundColor: 'white',
                  fontSize: '14px',
                  cursor: 'pointer'
                }}
              >
                <option value="">All Types</option>
                <option value="government">Government Bills (C-1 to C-200, S-1 to S-200)</option>
                <option value="private_member">Private Member Bills (C-201+, S-201+)</option>
                <option value="house">All House Bills (C-)</option>
                <option value="senate">All Senate Bills (S-)</option>
              </select>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <label style={{ 
                fontSize: '14px', 
                color: '#666', 
                fontWeight: '500',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                cursor: 'pointer'
              }}>
                <input
                  type="checkbox"
                  checked={hasVotesFilter}
                  onChange={(e) => setHasVotesFilter(e.target.checked)}
                  style={{
                    width: '16px',
                    height: '16px',
                    cursor: 'pointer'
                  }}
                />
                Bills with votes only
              </label>
            </div>
          </div>
        </div>

        {/* Filter Loading Notification */}
        {filterLoading && (
          <div style={{
            padding: '15px',
            backgroundColor: '#e3f2fd',
            border: '1px solid #90caf9',
            borderRadius: '6px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            color: '#1565c0'
          }}>
            <div style={{
              width: '20px',
              height: '20px',
              border: '2px solid #90caf9',
              borderTop: '2px solid #1565c0',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite'
            }}></div>
            <span>
              {hasVotesFilter ? 'Filtering bills with votes...' : 'Applying filters...'}
            </span>
            <style>{`
              @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
              }
            `}</style>
          </div>
        )}

        {/* Results Summary */}
        <div style={{ 
          fontSize: '14px', 
          color: '#666', 
          marginBottom: '20px' 
        }}>
          {activeSearch ? (
            <>Showing {bills.length} search results for "{activeSearch}"</>
          ) : (
            <>
              Showing {bills.length} of {totalCount} bills
              {sessionFilter && ` from session ${sessionFilter}`}
              {typeFilter && ` (${
                typeFilter === 'government' ? 'Government' : 
                typeFilter === 'private_member' ? 'Private Member' : 
                typeFilter === 'house' ? 'House' : 
                typeFilter === 'senate' ? 'Senate' : typeFilter
              } bills)`}
              {hasVotesFilter && ` with votes`}
            </>
          )}
        </div>
      </div>

      {/* Bills Grid */}
      <div 
        key={`bills-grid-${activeSearch}-${bills.length}`}
        style={{ 
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '12px',
          marginBottom: '30px',
          width: '100%'
        }}
        className="bills-grid"
      >
        <style>{`
          @media (min-width: 769px) {
            .bills-grid {
              display: grid !important;
              grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)) !important;
              justify-content: center !important;
              max-width: 1200px !important;
              margin: 0 auto !important;
            }
          }
        `}</style>
        {useMemo(() => bills.map((bill) => (
          <BillCard
            key={`${bill.session}-${bill.number}`}
            bill={bill}
            onClick={() => navigate(`/bill/${bill.session}/${bill.number}`)}
          />
        )), [bills, navigate])}
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
          {activeSearch ? (
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
      {hasMore && !activeSearch && bills.length > 0 && (
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