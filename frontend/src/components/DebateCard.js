import React from 'react';

function DebateCard({ debate, onClick }) {
  const handleClick = () => {
    if (onClick) {
      onClick();
    } else {
      // Navigate to OpenParliament.ca debates page by default
      const debateUrl = `https://openparliament.ca${debate.url}`;
      window.open(debateUrl, '_blank');
    }
  };

  const formatDate = (dateStr) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-CA', {
        year: 'numeric',
        month: 'long', 
        day: 'numeric',
        weekday: 'long'
      });
    } catch (e) {
      return dateStr;
    }
  };

  const formatShortDate = (dateStr) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-CA');
    } catch (e) {
      return dateStr;
    }
  };

  const getDebateColor = () => {
    // Color coding based on year for visual variety
    const year = debate.date ? new Date(debate.date).getFullYear() : 2024;
    const colors = {
      2025: '#007bff', // Current year - blue
      2024: '#20c997', // Recent - teal
      2023: '#6f42c1', // Past year - purple
      2022: '#fd7e14', // Older - orange
      2021: '#28a745', // Green
      default: '#6c757d' // Gray for older years
    };
    return colors[year] || colors.default;
  };

  const getDebateTypeLabel = () => {
    const year = debate.date ? new Date(debate.date).getFullYear() : 2024;
    if (year === 2025) return 'Current Session';
    if (year === 2024) return 'Recent Debate';
    if (year >= 2020) return 'Parliamentary Debate';
    return 'Historical Debate';
  };

  const formatDebateNumber = (debate) => {
    const year = debate.date ? new Date(debate.date).getFullYear() : '';
    return `${year} - #${debate.number}`;
  };

  return (
    <div
      onClick={handleClick}
      style={{
        border: '1px solid #ddd',
        borderRadius: '8px',
        padding: '20px',
        backgroundColor: 'white',
        boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
        cursor: 'pointer',
        transition: 'box-shadow 0.2s, transform 0.1s',
        width: '100%',
        height: '240px', // Fixed height for consistency with BillCard
        maxWidth: '400px',
        margin: '0',
        boxSizing: 'border-box',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between'
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
      {/* Top section - header and title */}
      <div style={{ flex: '1', display: 'flex', flexDirection: 'column' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'flex-start', 
          marginBottom: '10px',
          gap: '10px',
          flexWrap: 'wrap'
        }}>
          <div style={{
            padding: '4px 8px',
            backgroundColor: getDebateColor(),
            color: 'white',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: 'bold',
            whiteSpace: 'nowrap',
            flexShrink: 0
          }}>
            {getDebateTypeLabel()}
          </div>
          <div style={{
            fontSize: '14px',
            color: '#666',
            fontWeight: 'bold',
            textAlign: 'right',
            minWidth: 0
          }}>
            {formatDebateNumber(debate)}
          </div>
        </div>

        <h3 style={{
          margin: '0 0 8px 0',
          fontSize: '16px',
          lineHeight: '1.3',
          color: '#333',
          fontWeight: '600',
          wordBreak: 'break-word',
          overflow: 'hidden',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical'
        }}>
          Parliamentary Debate #{debate.number}
        </h3>

        <p style={{
          margin: '0 0 12px 0',
          fontSize: '14px',
          color: '#666',
          lineHeight: '1.4'
        }}>
          {formatDate(debate.date)}
        </p>

        {debate.most_frequent_word?.en && (
          <div style={{ marginBottom: '12px' }}>
            <span style={{ 
              display: 'inline-block',
              backgroundColor: '#e3f2fd',
              color: '#1565c0',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: '500'
            }}>
              Key topic: {debate.most_frequent_word.en}
            </span>
          </div>
        )}
      </div>

      {/* Bottom section - metadata and link */}
      <div style={{ marginTop: 'auto' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '13px',
          color: '#666',
          gap: '8px',
          flexWrap: 'wrap',
          marginBottom: '10px'
        }}>
          <span style={{ minWidth: 0 }}>
            <strong>Date:</strong> {formatShortDate(debate.date)}
          </span>
          <span style={{ 
            whiteSpace: 'nowrap',
            flexShrink: 0
          }}>
            <strong>Debate:</strong> #{debate.number}
          </span>
        </div>

        {/* External link */}
        <div style={{
          paddingTop: '10px',
          borderTop: '1px solid #e9ecef',
          display: 'flex',
          gap: '6px',
          flexWrap: 'wrap'
        }}>
          <a
            href={`https://openparliament.ca${debate.url}`}
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
            <span>🗣️</span>
            View Debate
            <span style={{ fontSize: '9px' }}>↗</span>
          </a>
        </div>
      </div>
    </div>
  );
}

export default DebateCard;