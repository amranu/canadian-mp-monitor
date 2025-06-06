import React, { useState } from 'react';
import MPList from './components/MPList';
import MPDetail from './components/MPDetail';

function App() {
  const [selectedMP, setSelectedMP] = useState(null);

  return (
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
        {selectedMP ? (
          <MPDetail 
            mp={selectedMP} 
            onBack={() => setSelectedMP(null)} 
          />
        ) : (
          <MPList onSelectMP={setSelectedMP} />
        )}
      </main>
    </div>
  );
}

export default App;