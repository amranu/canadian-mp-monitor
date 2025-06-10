import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, Link } from 'react-router-dom';
import MPList from './components/MPList';
import MPDetail from './components/MPDetail';
import VoteDetails from './components/VoteDetails';
import Bills from './components/Bills';
import BillDetail from './components/BillDetail';

// Component to scroll to top on route change
function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
}

function App() {
  return (
    <Router>
      <div style={{ backgroundColor: '#f5f5f5', minHeight: '100vh' }}>
        <header style={{ 
          backgroundColor: '#ffffff', 
          padding: '20px', 
          borderBottom: '1px solid #ddd',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h1 style={{ margin: 0, color: '#333' }}>Canadian MP Tracker</h1>
              <p style={{ margin: '5px 0 0 0', color: '#666' }}>
                Track your Members of Parliament and their voting records
              </p>
            </div>
            
            <nav style={{ display: 'flex', gap: '20px' }}>
              <Link 
                to="/" 
                style={{ 
                  color: '#007bff', 
                  textDecoration: 'none', 
                  fontSize: '16px',
                  fontWeight: '500',
                  padding: '8px 16px',
                  borderRadius: '4px',
                  transition: 'background-color 0.2s'
                }}
                onMouseEnter={(e) => e.target.style.backgroundColor = '#f8f9fa'}
                onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
              >
                MPs
              </Link>
              <Link 
                to="/bills" 
                style={{ 
                  color: '#007bff', 
                  textDecoration: 'none', 
                  fontSize: '16px',
                  fontWeight: '500',
                  padding: '8px 16px',
                  borderRadius: '4px',
                  transition: 'background-color 0.2s'
                }}
                onMouseEnter={(e) => e.target.style.backgroundColor = '#f8f9fa'}
                onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
              >
                Bills
              </Link>
            </nav>
          </div>
        </header>
        
        <main>
          <ScrollToTop />
          <Routes>
            <Route path="/" element={<MPList />} />
            <Route path="/mp/:mpSlug" element={<MPDetail />} />
            <Route path="/vote/:voteId" element={<VoteDetails />} />
            <Route path="/bills" element={<Bills />} />
            <Route path="/bill/:session/:number" element={<BillDetail />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;