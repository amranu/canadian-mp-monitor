import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

const SEOHead = ({ 
  title, 
  description, 
  keywords,
  ogTitle,
  ogDescription,
  ogImage,
  ogType = 'website',
  canonicalUrl,
  jsonLd
}) => {
  const location = useLocation();
  const baseUrl = 'https://mptracker.ca';
  const fullUrl = canonicalUrl || `${baseUrl}${location.pathname}`;
  
  useEffect(() => {
    // Set document title
    if (title) {
      document.title = title;
    }
    
    // Helper function to update or create meta tags
    const updateMetaTag = (name, content, property = false) => {
      if (!content) return;
      
      const selector = property ? `meta[property="${name}"]` : `meta[name="${name}"]`;
      let meta = document.querySelector(selector);
      
      if (!meta) {
        meta = document.createElement('meta');
        if (property) {
          meta.setAttribute('property', name);
        } else {
          meta.setAttribute('name', name);
        }
        document.head.appendChild(meta);
      }
      
      meta.setAttribute('content', content);
    };
    
    // Update canonical URL
    const updateCanonical = (url) => {
      let canonical = document.querySelector('link[rel="canonical"]');
      if (!canonical) {
        canonical = document.createElement('link');
        canonical.setAttribute('rel', 'canonical');
        document.head.appendChild(canonical);
      }
      canonical.setAttribute('href', url);
    };
    
    // Update JSON-LD structured data
    const updateJsonLd = (data) => {
      // Remove existing JSON-LD
      const existingJsonLd = document.querySelector('script[type="application/ld+json"]');
      if (existingJsonLd) {
        existingJsonLd.remove();
      }
      
      if (data) {
        const script = document.createElement('script');
        script.type = 'application/ld+json';
        script.textContent = JSON.stringify(data);
        document.head.appendChild(script);
      }
    };
    
    // Basic meta tags
    updateMetaTag('description', description);
    updateMetaTag('keywords', keywords);
    
    // Open Graph tags
    updateMetaTag('og:title', ogTitle || title, true);
    updateMetaTag('og:description', ogDescription || description, true);
    updateMetaTag('og:type', ogType, true);
    updateMetaTag('og:url', fullUrl, true);
    updateMetaTag('og:site_name', 'Canadian MP Tracker', true);
    updateMetaTag('og:locale', 'en_CA', true);
    
    if (ogImage) {
      updateMetaTag('og:image', ogImage, true);
      updateMetaTag('og:image:width', '1200', true);
      updateMetaTag('og:image:height', '630', true);
      updateMetaTag('og:image:alt', ogTitle || title, true);
    }
    
    // Twitter Card tags
    updateMetaTag('twitter:card', 'summary_large_image');
    updateMetaTag('twitter:title', ogTitle || title);
    updateMetaTag('twitter:description', ogDescription || description);
    if (ogImage) {
      updateMetaTag('twitter:image', ogImage);
    }
    
    // Additional meta tags
    updateMetaTag('author', 'Canadian MP Tracker');
    updateMetaTag('robots', 'index, follow');
    updateMetaTag('language', 'English');
    updateMetaTag('geo.region', 'CA');
    updateMetaTag('geo.country', 'Canada');
    
    // Update canonical URL
    updateCanonical(fullUrl);
    
    // Update JSON-LD structured data
    updateJsonLd(jsonLd);
    
  }, [title, description, keywords, ogTitle, ogDescription, ogImage, ogType, fullUrl, jsonLd]);
  
  return null;
};

export default SEOHead;