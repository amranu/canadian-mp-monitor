import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import MPList from './components/MPList';
import MPDetail from './components/MPDetail';
import VoteDetails from './components/VoteDetails';

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
          <h1 style={{ margin: 0, color: '#333' }}>Canadian MP Monitor</h1>
          <p style={{ margin: '5px 0 0 0', color: '#666' }}>
            Track your Members of Parliament and their voting records
          </p>
        </header>
        
        <main>
          <Routes>
            <Route path="/" element={<MPList />} />
            <Route path="/mp/:mpSlug" element={<MPDetail />} />
            <Route path="/vote/:voteId" element={<VoteDetails />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;