export function historyToDraft(item) {
  const plan = item.plan || {};
  const campaign = plan.campaign || {};
  const adGroup = plan.ad_group || {};
  const content = item.content || {};
  const budget = item.budget || {};
  const keywords = content.keywords || [...new Set((adGroup.keywords || []).map(k => k.text))];
  return {
    contentForm: {
      landing_page_url: item.landing_page_url || "",
      product_name: item.campaign_name || "",
      target_keywords: keywords.join("\n"),
      offer_identity: "", language: "English", tone: "Professional",
      target_audience: "", primary_offer: "", primary_cta: "", trust_signals: "",
    },
    campaignForm: {
      campaign_name: item.campaign_name || "Search Campaign",
      ad_group_name: item.ad_group_name || adGroup.name || "Search Campaign - Core",
      daily_budget_vnd: budget.daily_budget_vnd ?? plan.budget?.daily_budget_vnd ?? 300000,
      manual_cpc_bid_vnd: budget.manual_cpc_bid_vnd ?? plan.bidding?.manual_cpc_bid_vnd ?? 5000,
      currency_code: budget.currency_code || plan.budget?.currency_code || "VND",
      target_location: item.target_location || campaign.target_location || "Vietnam",
      excluded_locations: (campaign.excluded_locations || []).join("\n"),
      excluded_location_ids: (campaign.excluded_location_ids || []).join("\n"),
      keyword_match_types: [...new Set((adGroup.keywords || []).map(k => k.match_type || "EXACT"))].length
        ? [...new Set(adGroup.keywords.map(k => k.match_type || "EXACT"))] : ["EXACT"],
      search_partners: campaign.networks?.search_partners ?? true,
      display_network: campaign.networks?.display_network ?? false,
      schedule_enabled: false, scheduled_at: "",
      schedule_timezone: item.schedule?.timezone || "Asia/Saigon",
      enable_immediately: true, dry_run: true,
    },
    generated: {
      headlines: [...(content.headlines || [])],
      descriptions: [...(content.descriptions || [])],
    },
    selectedCustomerIds: [...(item.customer_ids || [])],
  };
}
