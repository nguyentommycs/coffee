export interface BeanProfile {
  id: string
  user_id: string
  created_at: string
  name: string
  roaster: string
  source_url?: string | null
  origin_country?: string | null
  origin_region?: string | null
  farm_or_cooperative?: string | null
  process?: 'Washed' | 'Natural' | 'Honey' | 'Anaerobic' | null
  variety?: string | null
  roast_level?: 'Light' | 'Medium-Light' | 'Medium' | 'Dark' | null
  tasting_notes: string[]
  user_score?: number | null
  user_notes?: string | null
  confidence: number
  missing_fields: string[]
  input_raw: string
  input_type: 'url' | 'name' | 'freeform'
}

export interface TasteProfile {
  user_id: string
  updated_at: string
  preferred_origins: string[]
  preferred_processes: string[]
  preferred_roast_levels: string[]
  flavor_affinities: string[]
  avoided_flavors: string[]
  narrative_summary: string
  total_beans_logged: number
  profile_confidence: number
}

export interface RecommendationCandidate {
  name: string
  roaster: string
  product_url: string
  origin_country?: string | null
  origin_region?: string | null
  process?: string | null
  roast_level?: string | null
  tasting_notes: string[]
  price_usd?: number | null
  in_stock?: boolean | null
  match_score: number
  match_rationale: string
}

export interface RecommendationResponse {
  user_id: string
  generated_at: string
  taste_profile: TasteProfile
  recommendations: RecommendationCandidate[]
  critic_notes: string
}

export interface RecommendationRun {
  id: string
  created_at: string
  critic_notes: string
  recommendations: RecommendationCandidate[]
  taste_profile_snapshot: TasteProfile
}
