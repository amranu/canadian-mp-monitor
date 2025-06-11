import React from 'react';

function DebateCard({ debate, onClick, showQuote = false, mpName = null }) {
  const handleClick = () => {
    if (onClick) {
      onClick();
    } else {
      // For MP-specific debates with quotes, prefer the speech URL
      // For general debates, use the debate URL
      let targetUrl;
      if (showQuote && debate.speech_url) {
        targetUrl = `https://openparliament.ca${debate.speech_url}`;
      } else if (debate.url) {
        targetUrl = `https://openparliament.ca${debate.url}`;
      } else {
        // Fallback for debates without proper URLs
        console.warn('No valid URL found for debate:', debate);
        return;
      }
      
      window.open(targetUrl, '_blank');
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
    // For debates, show just the year since they don't have traditional numbers
    return year ? `${year}` : 'Parliamentary Debate';
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
        height: '270px', // Fixed height for consistency with BillCard
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
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
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
            {debate.debate_category && debate.debate_category !== 'Parliamentary Business' && (
              <span style={{ 
                display: 'inline-block',
                backgroundColor: '#e8f5e8',
                color: '#2e7d32',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: '500'
              }}>
                {debate.debate_category}
              </span>
            )}
            {debate.procedural && (
              <span style={{ 
                display: 'inline-block',
                backgroundColor: '#fff3cd',
                color: '#856404',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                fontWeight: '500'
              }}>
                Procedural
              </span>
            )}
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
          WebkitLineClamp: showQuote ? 1 : 2,
          WebkitBoxOrient: 'vertical'
        }}>
          {debate.debate_title || `Parliamentary Debate #${debate.number}`}
        </h3>

        <p style={{
          margin: '0 0 12px 0',
          fontSize: '14px',
          color: '#666',
          lineHeight: '1.4'
        }}>
          {formatDate(debate.date)}
        </p>

        {/* MP Quote Section */}
        {showQuote && debate.content_preview && (
          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '12px',
            borderRadius: '4px',
            marginBottom: '12px',
            border: '1px solid #e9ecef'
          }}>
            <div style={{
              fontSize: '13px',
              color: '#495057',
              fontStyle: 'italic',
              lineHeight: '1.4',
              marginBottom: '8px'
            }}>
              "{debate.content_preview}..."
            </div>
            {mpName && (
              <div style={{
                fontSize: '12px',
                color: '#6c757d',
                fontWeight: '500'
              }}>
                — {mpName}
              </div>
            )}
          </div>
        )}

        {/* Key Topic Tag (if available) */}
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
          {showQuote && debate.speaking_time ? (
            <span style={{ 
              whiteSpace: 'nowrap',
              flexShrink: 0
            }}>
              <strong>~{Math.round(debate.speaking_time / 5)} words</strong>
            </span>
          ) : (
            <span style={{ 
              whiteSpace: 'nowrap',
              flexShrink: 0
            }}>
              <strong>Debate:</strong> #{debate.number}
            </span>
          )}
        </div>

      </div>
    </div>
  );
}

export default DebateCard;