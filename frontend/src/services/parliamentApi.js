import cache from './cache';

const API_BASE = process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:5000/api';

const headers = {
  'Accept': 'application/json'
};

export const parliamentApi = {
  async getMPs(limit = 50, offset = 0) {
    const cacheKey = `politicians-${limit}-${offset}`;
    
    // Check cache first
    const cachedData = cache.get(cacheKey);
    if (cachedData) {
      return cachedData;
    }
    
    const url = `${API_BASE}/politicians?limit=${limit}&offset=${offset}`;
    console.log('Fetching MPs from:', url);
    
    const response = await fetch(url, { headers });
    
    console.log('Response status:', response.status);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('API response:', data);
    
    // Cache the response
    cache.set(cacheKey, data);
    
    return data;
  },

  async getMP(url) {
    // Extract politician slug from the URL
    const slug = url.replace('/politicians/', '').replace('/', '');
    const response = await fetch(`${API_BASE}/politicians/${slug}`, { headers });
    return response.json();
  },

  async getVotes(limit = 20, offset = 0) {
    const cacheKey = `votes-${limit}-${offset}`;
    
    // Check cache first
    const cachedData = cache.get(cacheKey);
    if (cachedData) {
      return cachedData;
    }
    
    const response = await fetch(`${API_BASE}/votes?limit=${limit}&offset=${offset}`, { headers });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Cache the response
    cache.set(cacheKey, data);
    
    return data;
  },

  async getVoteDetails(url) {
    const response = await fetch(`${API_BASE}${url}`, { headers });
    return response.json();
  },

  async searchMPs(query) {
    const cacheKey = 'all-politicians';
    
    // Check cache first
    let data = cache.get(cacheKey);
    
    if (!data) {
      const response = await fetch(`${API_BASE}/politicians?limit=400`, { headers });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      data = await response.json();
      cache.set(cacheKey, data);
    }
    
    return {
      ...data,
      objects: data.objects.filter(mp => 
        mp.name.toLowerCase().includes(query.toLowerCase()) ||
        (mp.current_riding?.name?.en && mp.current_riding.name.en.toLowerCase().includes(query.toLowerCase())) ||
        (mp.current_party?.short_name?.en && mp.current_party.short_name.en.toLowerCase().includes(query.toLowerCase()))
      )
    };
  },

  async getMPVotes(mpUrl, limit = 1000, offset = 0) {
    const slug = mpUrl.replace('/politicians/', '').replace('/', '');
    const cacheKey = `mp-votes-${slug}-${limit}-${offset}`;
    
    // Check cache first, but only if we're not looking for loading responses
    const cachedData = cache.get(cacheKey);
    if (cachedData && !cachedData.loading) {
      return cachedData;
    }
    
    const response = await fetch(`${API_BASE}/politician/${slug}/votes?limit=${limit}&offset=${offset}`, { headers });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Only cache if we have actual vote data (not loading state)
    if (!data.loading && data.objects && data.objects.length > 0) {
      cache.set(cacheKey, data);
    }
    
    return data;
  },

  async getVoteDetails(voteUrl) {
    // Handle different URL formats: /votes/45-1/4/ or 45-1/4
    let votePath = voteUrl;
    if (votePath.startsWith('/votes/')) {
      votePath = votePath.replace('/votes/', '');
    }
    if (votePath.endsWith('/')) {
      votePath = votePath.slice(0, -1);
    }
    
    const cacheKey = `vote-details-${votePath}`;
    
    console.log('Loading vote details for:', votePath);
    
    // Check cache first
    const cachedData = cache.get(cacheKey);
    if (cachedData) {
      console.log('Serving cached vote details');
      return cachedData;
    }
    
    const url = `${API_BASE}/votes/${votePath}/details`;
    console.log('Fetching vote details from:', url);
    
    const response = await fetch(url, { headers });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('Vote details fetch error:', response.status, errorText);
      throw new Error(`HTTP error! status: ${response.status} - ${errorText}`);
    }
    
    const data = await response.json();
    console.log('Vote details loaded:', data);
    
    // Cache the response
    cache.set(cacheKey, data);
    
    return data;
  },

  // Cache management methods
  clearCache() {
    cache.clear();
  },

  clearCacheKey(key) {
    cache.clear(key);
  },

  getCacheStatus() {
    return cache.getStatus();
  },

  async getVoteBallots(voteUrl) {
    const response = await fetch(`${API_BASE}/votes/ballots?vote=${voteUrl}&limit=400`, { headers });
    
    if (!response.ok) {
      throw new Error(`Failed to fetch vote ballots: ${response.status}`);
    }
    
    return response.json();
  },

  async getBills(limit = 20, offset = 0, filters = {}) {
    const cacheKey = `bills-${limit}-${offset}-${JSON.stringify(filters)}`;
    
    // Check cache first
    const cachedData = cache.get(cacheKey);
    if (cachedData) {
      return cachedData;
    }
    
    // Build query parameters
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    
    if (filters.session) {
      params.append('session', filters.session);
    }
    
    if (filters.sponsor) {
      params.append('sponsor', filters.sponsor);
    }
    
    if (filters.type) {
      params.append('type', filters.type);
    }
    
    if (filters.has_votes) {
      params.append('has_votes', filters.has_votes);
    }
    
    const url = `${API_BASE}/bills?${params.toString()}`;
    console.log('Fetching bills from:', url);
    
    const response = await fetch(url, { headers });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Bills API response:', data);
    
    // Cache the response
    cache.set(cacheKey, data);
    
    return data;
  },

  async getBill(session, number) {
    const billPath = `${session}/${number}`;
    const cacheKey = `bill-${billPath}`;
    
    // Check cache first
    const cachedData = cache.get(cacheKey);
    if (cachedData) {
      return cachedData;
    }
    
    const url = `${API_BASE}/bills/${billPath}`;
    console.log('Fetching bill from:', url);
    
    const response = await fetch(url, { headers });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Bill details loaded:', data);
    
    // Cache the response
    cache.set(cacheKey, data);
    
    return data;
  },

  async searchBills(query, filters = {}) {
    // Get all bills with filters and search locally
    // This could be optimized with backend search in the future
    const data = await this.getBills(1000, 0, filters);
    
    if (!query) {
      return data;
    }
    
    const filteredBills = data.objects.filter(bill => {
      const searchText = query.toLowerCase();
      return (
        bill.name?.en?.toLowerCase().includes(searchText) ||
        bill.name?.fr?.toLowerCase().includes(searchText) ||
        bill.number?.toLowerCase().includes(searchText)
      );
    });
    
    return {
      ...data,
      objects: filteredBills,
      total_count: filteredBills.length
    };
  },

  async getBillVotes(session, number) {
    const billPath = `${session}/${number}`;
    const cacheKey = `bill-votes-${billPath}`;
    
    // Check cache first
    const cachedData = cache.get(cacheKey);
    if (cachedData) {
      return cachedData;
    }
    
    const url = `${API_BASE}/bills/${billPath}/votes`;
    console.log('Fetching bill votes from:', url);
    
    const response = await fetch(url, { headers });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Bill votes loaded:', data);
    
    // Cache the response
    cache.set(cacheKey, data);
    
    return data;
  }
};