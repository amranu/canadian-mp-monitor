import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { parliamentApi } from '../services/parliamentApi';
import DebateCard from './DebateCard';
import SEOHead from './SEOHead';

function Debates() {
  const navigate = useNavigate();
  const [debates, setDebates] = useState([]);
  const [allDebates, setAllDebates] = useState([]);
  
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [activeSearch, setActiveSearch] = useState('');
  const [yearFilter, setYearFilter] = useState('');
  const [availableYears, setAvailableYears] = useState([]);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [filterLoading, setFilterLoading] = useState(false);

  useEffect(() => {
    loadDebates();
  }, [yearFilter]);

  // Search filtering
  useEffect(() => {
    if (!allDebates.length) return;
    
    let filteredDebates = allDebates;
    
    // Apply search query filter
    if (activeSearch.trim()) {
      const query = activeSearch.toLowerCase();
      filteredDebates = filteredDebates.filter(debate => 
        debate.most_frequent_word?.en?.toLowerCase().includes(query) ||
        debate.date?.toLowerCase().includes(query) ||
        debate.number?.toString().includes(query)
      );
    }
    
    setDebates(filteredDebates);
    setTotalCount(filteredDebates.length);
    setHasMore(false);
  }, [activeSearch, allDebates]);

  const loadDebates = async (resetOffset = true) => {
    try {
      setLoading(true);
      if (resetOffset) {
        setFilterLoading(true);
      }
      
      // Load all debates to enable real-time search and filtering
      const data = await parliamentApi.getDebates(1000, 0); // Load first 1000 debates
      
      let filteredData = data.objects;
      
      // Apply year filter
      if (yearFilter) {
        filteredData = filteredData.filter(debate => 
          debate.date && debate.date.startsWith(yearFilter)
        );
      }
      
      setAllDebates(filteredData);
      setTotalCount(data.total_count || filteredData.length);
      setHasMore(false); // Disable pagination since we load all debates
      setOffset(0);
      
      // Extract available years (only do this once on initial load)
      if (!availableYears.length) {
        const years = [...new Set(data.objects.map(debate => {
          if (debate.date) {
            return debate.date.split('-')[0];
          }
          return null;
        }).filter(Boolean))].sort().reverse();
        setAvailableYears(years);
      }
      
    } catch (error) {
      console.error('Error loading debates:', error);
    } finally {
      setLoading(false);
      setFilterLoading(false);
    }
  };

  const handleSearch = () => {
    setActiveSearch(searchInput);
    setSearchQuery(searchInput);
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


  const debatesJsonLd = {
    "@context": "https://schema.org",
    "@type": "DataCatalog",
    "name": "Canadian Parliamentary Debates",
    "description": "Complete database of debates from the Canadian Parliament",
    "url": "https://mptracker.ca/debates",
    "publisher": {
      "@type": "WebApplication",
      "name": "Canadian MP Monitor"
    },
    "about": {
      "@type": "GovernmentOrganization",
      "name": "Parliament of Canada"
    }
  };

  return (
    <>
      <SEOHead 
        title="Canadian Parliamentary Debates - Track Parliamentary Discussions | Canadian MP Tracker"
        description={`Browse and search ${totalCount} parliamentary debates from the Canadian Parliament. Explore parliamentary discussions, key topics, and legislative proceedings.`}
        keywords="Canadian debates, parliamentary debates, Parliament discussions, House of Commons debates, parliamentary proceedings, Canadian politics"
        ogTitle="Canadian Parliamentary Debates Database"
        ogDescription={`Complete database of ${totalCount} debates from the Canadian Parliament with key topics and discussion summaries.`}
        jsonLd={debatesJsonLd}
      />
      <div style={{ padding: '20px' }}>
        <div style={{ marginBottom: '30px' }}>
          <h1 style={{ margin: '0 0 10px 0' }}>Parliamentary Debates</h1>
          <p style={{ color: '#666', marginBottom: '20px' }}>
            Browse and search debates from the Canadian Parliament
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
                placeholder="Search debates by topic, date, or number..."
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
                  Year:
                </label>
                <select
                  value={yearFilter}
                  onChange={(e) => setYearFilter(e.target.value)}
                  style={{
                    padding: '8px 12px',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    backgroundColor: 'white',
                    fontSize: '14px',
                    cursor: 'pointer'
                  }}
                >
                  <option value="">All Years</option>
                  {availableYears.map(year => (
                    <option key={year} value={year}>
                      {year}
                    </option>
                  ))}
                </select>
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
              <span>Applying filters...</span>
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
              <>Showing {debates.length} search results for "{activeSearch}"</>
            ) : (
              <>
                Showing {debates.length} of {totalCount} debates
                {yearFilter && ` from ${yearFilter}`}
              </>
            )}
          </div>
        </div>

        {/* Debates Grid */}
        <div 
          key={`debates-grid-${activeSearch}-${debates.length}`}
          style={{ 
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px',
            marginBottom: '30px',
            width: '100%'
          }}
          className="debates-grid"
        >
          <style>{`
            @media (min-width: 769px) {
              .debates-grid {
                display: grid !important;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)) !important;
                justify-content: center !important;
              }
            }
          `}</style>
          {useMemo(() => debates.map((debate) => (
            <DebateCard
              key={`${debate.date}-${debate.number}`}
              debate={debate}
            />
          )), [debates])}
        </div>

        {/* Loading State */}
        {loading && debates.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
            Loading debates...
          </div>
        )}

        {/* No Results */}
        {!loading && debates.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
            {activeSearch ? (
              <>
                <h3>No debates found</h3>
                <p>No debates match your search criteria. Try adjusting your search terms or filters.</p>
              </>
            ) : (
              <>
                <h3>No debates available</h3>
                <p>No debates are currently available for the selected year.</p>
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}

export default Debates;