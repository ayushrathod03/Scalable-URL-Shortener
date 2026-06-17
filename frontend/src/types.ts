export interface URLResponse {
  short_token: string;
  short_url: string;
  long_url: string;
  created_at: string;
  expires_at: string | null;
}

export interface DailyClickCount {
  date: string;
  clicks: number;
}

export interface CountryClickCount {
  country: string;
  clicks: number;
}

export interface URLAnalyticsResponse {
  short_token: string;
  long_url: string;
  created_at: string;
  expires_at: string | null;
  total_clicks: number;
  clicks_over_time: DailyClickCount[];
  geo_distribution: CountryClickCount[];
}

export interface GlobalAnalyticsResponse {
  total_urls: number;
  total_clicks: number;
  clicks_over_time: DailyClickCount[];
  geo_distribution: CountryClickCount[];
}
