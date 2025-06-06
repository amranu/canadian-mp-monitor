import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { parliamentApi } from '../services/parliamentApi';

function MPList() {
  const navigate = useNavigate();
  const [allMPs, setAllMPs] = useState([]);
  const [filteredMPs, setFilteredMPs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadAllMPs();
  }, []);

  const loadAllMPs = async () => {
    try {
      setLoading(true);
      console.log('Starting to load MPs...');
      
      let allMPs = [];
      let offset = 0;
      const limit = 100;
      let hasMoreData = true;

      while (hasMoreData) {
        console.log(`Loading MPs: offset=${offset}, limit=${limit}`);
        const data = await parliamentApi.getMPs(limit, offset);
        console.log(`Received ${data.objects.length} MPs`);
        
        allMPs = [...allMPs, ...data.objects];
        hasMoreData = data.pagination.next_url !== null;
        offset += limit;
        
        // Safety break to avoid infinite loops
        if (offset > 1000) {
          console.log('Safety break: offset > 1000');
          break;
        }
      }

      console.log(`Total MPs loaded: ${allMPs.length}`);
      setAllMPs(allMPs);
      setFilteredMPs(allMPs);
    } catch (error) {
      console.error('Error loading MPs:', error);
      console.error('Error details:', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (query) => {
    setSearchQuery(query);
    
    if (!query.trim()) {
      setFilteredMPs(allMPs);
      return;
    }

    const filtered = allMPs.filter(mp => 
      mp.name.toLowerCase().includes(query.toLowerCase()) ||
      (mp.current_riding?.name?.en && mp.current_riding.name.en.toLowerCase().includes(query.toLowerCase())) ||
      (mp.current_riding?.province && mp.current_riding.province.toLowerCase().includes(query.toLowerCase())) ||
      (mp.current_party?.short_name?.en && mp.current_party.short_name.en.toLowerCase().includes(query.toLowerCase()))
    );
    
    setFilteredMPs(filtered);
  };

  const clearSearch = () => {
    setSearchQuery('');
    setFilteredMPs(allMPs);
  };

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ marginBottom: '20px' }}>
        <h2>
          {searchQuery ? 
            `Search Results: ${filteredMPs.length} of ${allMPs.length} MPs` : 
            `All Members of Parliament (${allMPs.length} MPs)`
          }
        </h2>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
          <input
            type="text"
            placeholder="Search MPs by name, riding, province, or party..."
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            style={{ 
              flex: 1, 
              padding: '10px', 
              border: '1px solid #ddd', 
              borderRadius: '4px' 
            }}
          />
          {searchQuery && (
            <button 
              onClick={clearSearch}
              style={{ 
                padding: '10px 20px', 
                backgroundColor: '#6c757d', 
                color: 'white', 
                border: 'none', 
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '15px' }}>
        {filteredMPs.map((mp) => (
          <div 
            key={mp.url} 
            onClick={() => {
              const mpSlug = mp.url.replace('/politicians/', '').replace('/', '');
              navigate(`/mp/${mpSlug}`);
            }}
            style={{
              border: '1px solid #ddd',
              borderRadius: '8px',
              padding: '15px',
              cursor: 'pointer',
              backgroundColor: 'white',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
              transition: 'box-shadow 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.boxShadow = '0 4px 8px rgba(0,0,0,0.15)'}
            onMouseLeave={(e) => e.target.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)'}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
              {mp.image && (
                <img 
                  src={`https://openparliament.ca${mp.image}`}
                  alt={mp.name}
                  style={{ 
                    width: '60px', 
                    height: '60px', 
                    borderRadius: '50%', 
                    objectFit: 'cover' 
                  }}
                />
              )}
              <div>
                <h3 style={{ margin: '0 0 5px 0', fontSize: '16px' }}>{mp.name}</h3>
                <p style={{ margin: '2px 0', color: '#666', fontSize: '14px' }}>
                  {mp.current_party?.short_name?.en}
                </p>
                <p style={{ margin: '2px 0', color: '#666', fontSize: '14px' }}>
                  {mp.current_riding?.name?.en}, {mp.current_riding?.province}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '20px' }}>
          Loading MPs... This may take a moment.
        </div>
      )}

      {!loading && allMPs.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <h3>No MPs loaded</h3>
          <p>There may be a network issue or CORS problem with the API.</p>
          <p>Check the browser console for error details.</p>
          <button 
            onClick={loadAllMPs}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: '#007bff', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Retry Loading MPs
          </button>
        </div>
      )}

      {!loading && allMPs.length > 0 && filteredMPs.length === 0 && searchQuery && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <h3>No MPs match your search</h3>
          <p>Try searching for a different name, riding, province, or party.</p>
          <button 
            onClick={clearSearch}
            style={{ 
              padding: '10px 20px', 
              backgroundColor: '#007bff', 
              color: 'white', 
              border: 'none', 
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Show All MPs
          </button>
        </div>
      )}

    </div>
  );
}

export default MPList;