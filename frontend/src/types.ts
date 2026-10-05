export type Fields = {
  brand: string | null;
  width_mm: number | null;
  aspect_ratio: number | null;
  construction: "radial" | "diagonal" | "belted" | null;
  rim_inches: number | null;
  load_index: number | null;
  speed_rating: string | null;
  dot_code: string | null;
  manufacture_week: number | null;
  manufacture_year: number | null;
};
export type Citation = {
  chunk_id: string;
  document: string;
  page: number | null;
  text: string;
  source_url: string | null;
  score: number;
};
export type Scan = {
  id: string;
  filename: string;
  created_at: string;
  image_url: string;
  width: number;
  height: number;
  detections: {
    text: string;
    confidence: number | null;
    polygon: number[][];
  }[];
  raw_text: string;
  original_fields: Fields;
  fields: Fields;
  parse_warnings: string[];
  correction_count: number;
  references: Citation[];
  retrieval_warning: string | null;
  messages: { role: string; content: string }[];
};
export type Health = {
  ocr: { ready: boolean; detail: string };
  retrieval: { ready: boolean; detail: string };
  llm: { ready: boolean; detail: string };
  provider: string;
};
export type Reply = {
  answer: string;
  generated: boolean;
  citations: Citation[];
  warning: string | null;
};
