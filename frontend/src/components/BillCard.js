import React from 'react';
import { useNavigate } from 'react-router-dom';

function BillCard({ bill, onClick }) {
  const navigate = useNavigate();

  const handleClick = () => {
    if (onClick) {
      onClick();
    } else {
      navigate(`/bill/${bill.session}/${bill.number}`);
    }
  };

  const getBillTypeColor = (number) => {
    if (number.startsWith('C-')) {
      const billNum = parseInt(number.substring(2));
      return billNum <= 200 ? '#007bff' : '#20c997'; // Government bills - blue, Private member bills - teal
    }
    if (number.startsWith('S-')) {
      const billNum = parseInt(number.substring(2));
      return billNum <= 200 ? '#6f42c1' : '#fd7e14'; // Government Senate bills - purple, Private Senate bills - orange
    }
    if (number.startsWith('M-')) return '#28a745'; // Private member motions - green
    return '#6c757d'; // Other - gray
  };

  const getBillTypeLabel = (number) => {
    if (number.startsWith('C-')) {
      const billNum = parseInt(number.substring(2));
      return billNum <= 200 ? 'Government Bill' : 'Private Member Bill';
    }
    if (number.startsWith('S-')) {
      const billNum = parseInt(number.substring(2));
      return billNum <= 200 ? 'Senate Bill' : 'Private Senate Bill';
    }
    if (number.startsWith('M-')) return 'Private Motion';
    return 'Other';
  };

  const formatBillNumber = (bill) => {
    return `${bill.session} - ${bill.number}`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString('en-CA');
  };

  return (
    <div
      onClick={handleClick}
      style={{
        border: '1px solid #ddd',
        borderRadius: '8px',
        padding: '16px',
        backgroundColor: 'white',
        boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
        cursor: 'pointer',
        transition: 'box-shadow 0.2s, transform 0.1s',
        minWidth: 0, // Allow shrinking below content size
        width: '100%',
        maxWidth: '400px', // Prevent cards from getting too wide on large screens
        margin: '0 auto' // Center the card within its grid cell
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 4px 8px rgba(0,0,0,0.1)';
        e.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      <div style={{ marginBottom: '12px' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'flex-start', 
          marginBottom: '8px',
          gap: '8px',
          flexWrap: 'wrap'
        }}>
          <div style={{
            padding: '4px 8px',
            backgroundColor: getBillTypeColor(bill.number),
            color: 'white',
            borderRadius: '4px',
            fontSize: '11px',
            fontWeight: 'bold',
            whiteSpace: 'nowrap',
            flexShrink: 0
          }}>
            {getBillTypeLabel(bill.number)}
          </div>
          <div style={{
            fontSize: '13px',
            color: '#666',
            fontWeight: 'bold',
            textAlign: 'right',
            minWidth: 0 // Allow text to wrap if needed
          }}>
            {formatBillNumber(bill)}
          </div>
        </div>

        <h3 style={{
          margin: '0 0 8px 0',
          fontSize: '16px',
          lineHeight: '1.3',
          color: '#333',
          fontWeight: '600',
          wordBreak: 'break-word' // Handle long titles
        }}>
          {bill.name?.en || 'Bill name not available'}
        </h3>

        {bill.name?.fr && bill.name.fr !== bill.name?.en && (
          <p style={{
            margin: '0 0 8px 0',
            fontSize: '13px',
            color: '#666',
            fontStyle: 'italic',
            lineHeight: '1.2',
            wordBreak: 'break-word'
          }}>
            {bill.name.fr}
          </p>
        )}
      </div>

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: '12px',
        color: '#666',
        gap: '8px',
        flexWrap: 'wrap'
      }}>
        <span style={{ minWidth: 0 }}>
          <strong>Introduced:</strong> {formatDate(bill.introduced)}
        </span>
        <span style={{ 
          whiteSpace: 'nowrap',
          flexShrink: 0
        }}>
          <strong>Session:</strong> {bill.session}
        </span>
      </div>

      {/* LEGISinfo Link */}
      {bill.legisinfo_id && (
        <div style={{
          marginTop: '10px',
          paddingTop: '10px',
          borderTop: '1px solid #e9ecef'
        }}>
          <a
            href={`https://www.parl.ca/legisinfo/en/bill/${bill.session}/${bill.number.toLowerCase()}`}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              color: '#007bff',
              textDecoration: 'none',
              fontSize: '11px',
              fontWeight: '500',
              padding: '3px 6px',
              backgroundColor: '#f8f9fa',
              borderRadius: '3px',
              border: '1px solid #dee2e6',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#e3f2fd';
              e.currentTarget.style.borderColor = '#90caf9';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = '#f8f9fa';
              e.currentTarget.style.borderColor = '#dee2e6';
            }}
          >
            <span>🏛️</span>
            Official Bill Details
            <span style={{ fontSize: '9px' }}>↗</span>
          </a>
        </div>
      )}
    </div>
  );
}

export default BillCard;