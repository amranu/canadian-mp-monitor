#!/usr/bin/env python3
"""
Patch to fix LEGISinfo enrichment function
"""

def enrich_bill_with_legisinfo_fixed(bill, fetch_legisinfo_data_func):
    """Fixed version of enrich_bill_with_legisinfo"""
    if not bill.get('session') or not bill.get('number'):
        return bill
    
    legis_data = fetch_legisinfo_data_func(bill['session'], bill['number'])
    if legis_data:
        # Add relevant LEGISinfo fields to the bill
        enriched_bill = bill.copy()
        
        # Handle both list and dict responses from LEGISinfo API
        if isinstance(legis_data, list) and len(legis_data) > 0:
            # Take the first item if it's a list
            legis_info = legis_data[0]
        elif isinstance(legis_data, dict):
            legis_info = legis_data
        else:
            # If we can't parse the response, return original bill
            return bill
        
        enriched_bill['legis_summary'] = legis_info.get('ShortLegislativeSummaryEn')
        enriched_bill['legis_status'] = legis_info.get('StatusNameEn')
        enriched_bill['legis_sponsor'] = legis_info.get('SponsorPersonName')
        enriched_bill['legis_sponsor_title'] = legis_info.get('SponsorAffiliationTitle')
        enriched_bill['royal_assent_date'] = legis_info.get('ReceivedRoyalAssentDateTime')
        enriched_bill['legis_url'] = f"https://www.parl.ca/legisinfo/en/bill/{bill['session']}/{bill['number'].lower()}"
        return enriched_bill
    
    return bill

if __name__ == "__main__":
    print("LEGISinfo enrichment fix applied")