'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
  MapPin,
  Sprout,
  Calendar,
  Layers,
  FlaskConical,
  Upload,
  X,
  Image as ImageIcon,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ShieldCheck,
  ChevronDown,
  FileCheck,
  FileText,
} from 'lucide-react';
import { StatusBadge } from './StatusBadge';

const CROP_CATEGORIES: Record<string, string[]> = {
  Vegetables: ['Tomato', 'Potato', 'Chilli', 'Onion', 'Brinjal', 'Cabbage', 'Cauliflower', 'Okra'],
  Cereals: ['Rice', 'Wheat', 'Maize', 'Millets', 'Barley'],
  Pulses: ['Chickpea', 'Pigeonpea', 'Soybean', 'Groundnut', 'Blackgram', 'Greengram'],
  Oilseeds: ['Mustard', 'Sunflower', 'Sesame'],
  Fruits: ['Apple', 'Banana', 'Mango', 'Citrus', 'Grapes'],
  'Commercial Crops': ['Cotton', 'Sugarcane', 'Tobacco', 'Tea', 'Coffee'],
};

const STAGES = [
  { id: 'seedling', label: 'Seedling' },
  { id: 'vegetative', label: 'Vegetative' },
  { id: 'flowering', label: 'Flowering' },
  { id: 'fruiting_grain_filling', label: 'Fruiting / Grain Filling' },
  { id: 'maturity', label: 'Maturity' },
  { id: 'harvest', label: 'Harvest' },
  { id: 'unknown', label: 'Unknown / General' },
];

const SOIL_TYPES = [
  'Red Soil',
  'Black Soil',
  'Alluvial',
  'Sandy Loam',
  'Clay Loam',
  'Loam',
  'Sandy',
  'Clay',
  'Laterite',
  'Unknown',
];

interface FarmInputFormProps {
  apiBase: string;
  onRunAdvisory: (payload: {
    crop: string;
    growthStage: string;
    locationName: string;
    lat: number | null;
    lon: number | null;
    soilMode: 'automatic' | 'manual' | 'measured' | 'report';
    soilType: string;
    n: string;
    p: string;
    k: string;
    farmArea: string;
    irrigationMethod: string;
    sowingDate: string;
    currentPrice: string;
    priceHistory: string;
    image: File | null;
    diseaseModel?: string;
    leafCropSelection?: string;
  }) => void;
  loading: boolean;
  error?: string;
}

export function FarmInputForm({
  apiBase,
  onRunAdvisory,
  loading,
  error,
}: FarmInputFormProps) {
  // Model Selection & Leaf Crop Conditioning (DINOv2 LoRA is now the active default)
  const [diseaseModel, setDiseaseModel] = useState<'dinov2_lora' | 'production'>('dinov2_lora');
  const [leafCropSelection, setLeafCropSelection] = useState<string>('none');

  // Farm Location
  const [locationQuery, setLocationQuery] = useState('Madurai, Tamil Nadu');
  const [selectedLocation, setSelectedLocation] = useState<{
    name: string;
    lat: number | null;
    lon: number | null;
  }>({
    name: 'Madurai, Tamil Nadu, India',
    lat: 9.9252,
    lon: 78.1198,
  });
  const [locationResults, setLocationResults] = useState<any[]>([]);
  const [showLocationDropdown, setShowLocationDropdown] = useState(false);

  // Crop & Stage
  const [crop, setCrop] = useState('Tomato');
  const [growthStage, setGrowthStage] = useState('vegetative');

  // Soil Mode
  const [soilMode, setSoilMode] = useState<'automatic' | 'manual' | 'measured' | 'report'>('automatic');
  const [soilType, setSoilType] = useState('Red Soil');
  const [n, setN] = useState('');
  const [p, setP] = useState('');
  const [k, setK] = useState('');

  // Soil Report File State (Mode D)
  const [soilReportFile, setSoilReportFile] = useState<File | null>(null);
  const [soilReportDragOver, setSoilReportDragOver] = useState(false);
  const soilReportInputRef = useRef<HTMLInputElement>(null);

  // Optional Context
  const [farmArea, setFarmArea] = useState('2.5');
  const [irrigationMethod, setIrrigationMethod] = useState('Drip');
  const [sowingDate, setSowingDate] = useState('');
  const [currentPrice, setCurrentPrice] = useState('2000');
  const [priceHistory, setPriceHistory] = useState('1950,1980,2000');
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSoilReportChange = (file: File | null) => {
    setSoilReportFile(file);
    if (!file && soilReportInputRef.current) {
      soilReportInputRef.current.value = '';
    }
  };

  // Location search autocomplete
  useEffect(() => {
    if (!locationQuery || locationQuery.length < 2) {
      setLocationResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`${apiBase}/api/location/search?q=${encodeURIComponent(locationQuery)}`);
        if (res.ok) {
          const data = await res.json();
          setLocationResults(data.results || []);
        }
      } catch {
        // Fallback silently
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [locationQuery, apiBase]);

  // Image Preview
  const handleImageChange = (file: File | null) => {
    setImage(file);
    if (file) {
      const url = URL.createObjectURL(file);
      setImagePreview(url);
    } else {
      setImagePreview(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onRunAdvisory({
      crop,
      growthStage,
      locationName: selectedLocation.name || locationQuery,
      lat: selectedLocation.lat,
      lon: selectedLocation.lon,
      soilMode,
      soilType: soilMode === 'manual' ? soilType : '',
      n: soilMode === 'measured' ? n : '',
      p: soilMode === 'measured' ? p : '',
      k: soilMode === 'measured' ? k : '',
      farmArea,
      irrigationMethod,
      sowingDate,
      currentPrice,
      priceHistory,
      image,
      diseaseModel,
      leafCropSelection: leafCropSelection === 'auto' ? crop : (leafCropSelection === 'none' ? '' : leafCropSelection),
    });
  };

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <span className="eyebrow">FIELD TELEMETRY INPUT</span>
          <h2 style={{ fontSize: '17px', margin: '2px 0 0' }}>Farm Scenario Parameters</h2>
        </div>
        <StatusBadge label="VERIFIED GEOCODING" variant="brand" icon="check" size="sm" />
      </div>

      <form onSubmit={handleSubmit} className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* ---------------- SECTION 1: FARM DETAILS ---------------- */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
            <MapPin size={16} color="var(--forest-primary)" />
            <h3 style={{ fontSize: '14px', fontWeight: 700, margin: 0 }}>1. Farm & Location Details</h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* Location Autocomplete */}
            <div style={{ position: 'relative' }}>
              <label className="form-label">
                <span>Farm Location (Village / District / State)</span>
                {selectedLocation.name && (
                  <span style={{ fontSize: '11px', color: 'var(--forest-primary)', fontWeight: 600 }}>
                    ✓ Resolved
                  </span>
                )}
              </label>
              <input
                className="input"
                value={locationQuery}
                placeholder="e.g. Madurai, Tamil Nadu or Nashik, Maharashtra"
                onChange={e => {
                  setLocationQuery(e.target.value);
                  setShowLocationDropdown(true);
                }}
                onFocus={() => setShowLocationDropdown(true)}
              />

              {showLocationDropdown && locationResults.length > 0 && (
                <div
                  style={{
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    right: 0,
                    zIndex: 50,
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-sm)',
                    boxShadow: 'var(--shadow-md)',
                    maxHeight: '220px',
                    overflowY: 'auto',
                    marginTop: '4px',
                  }}
                >
                  {locationResults.map((loc, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '9px 12px',
                        borderBottom: '1px solid var(--border-subtle)',
                        cursor: 'pointer',
                        fontSize: '12.5px',
                      }}
                      onMouseDown={() => {
                        setSelectedLocation({
                          name: loc.display_name,
                          lat: loc.latitude,
                          lon: loc.longitude,
                        });
                        setLocationQuery(loc.display_name);
                        setShowLocationDropdown(false);
                      }}
                    >
                      <strong style={{ display: 'block', color: 'var(--text-primary)' }}>{loc.name}</strong>
                      <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{loc.display_name}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Crop & Growth Stage */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label className="form-label">Selected Crop</label>
                <select className="select" value={crop} onChange={e => setCrop(e.target.value)}>
                  {Object.entries(CROP_CATEGORIES).map(([cat, crops]) => (
                    <optgroup key={cat} label={`── ${cat} ──`}>
                      {crops.map(c => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>

              <div>
                <label className="form-label">Growth Stage</label>
                <select className="select" value={growthStage} onChange={e => setGrowthStage(e.target.value)}>
                  {STAGES.map(s => (
                    <option key={s.id} value={s.id}>{s.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Optional Area & Irrigation */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
              <div>
                <label className="form-label">Farm Area (acres)</label>
                <input
                  type="number"
                  step="0.1"
                  className="input"
                  placeholder="e.g. 2.5"
                  value={farmArea}
                  onChange={e => setFarmArea(e.target.value)}
                />
              </div>

              <div>
                <label className="form-label">Irrigation Method</label>
                <select className="select" value={irrigationMethod} onChange={e => setIrrigationMethod(e.target.value)}>
                  <option value="Drip">Drip Irrigation</option>
                  <option value="Furrow / Flood">Furrow / Flood</option>
                  <option value="Sprinkler">Sprinkler</option>
                  <option value="Rainfed">Rainfed</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* ---------------- SECTION 2: SOIL INFORMATION ---------------- */}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FlaskConical size={16} color="var(--forest-primary)" />
              <h3 style={{ fontSize: '14px', fontWeight: 700, margin: 0 }}>2. Soil Nutrient Input Method</h3>
            </div>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                color: soilMode === 'measured' ? 'var(--semantic-success)' : (soilMode === 'report' ? '#d97706' : 'var(--text-muted)'),
              }}
            >
              {soilMode === 'measured' ? 'HIGHER CONFIDENCE (MEASURED)' : (soilMode === 'report' ? 'REPORT ATTACHED (EXTRACTION PENDING)' : (soilMode === 'manual' ? 'MODERATE CONFIDENCE' : 'ESTIMATED / MODERATE'))}
            </span>
          </div>

          {/* Mode Selector Buttons */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', marginBottom: '10px' }}>
            <button
              type="button"
              className={`btn btn-sm ${soilMode === 'automatic' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ fontSize: '11.5px', justifyContent: 'flex-start', textAlign: 'left', padding: '8px 10px' }}
              onClick={() => setSoilMode('automatic')}
            >
              <div>
                <div style={{ fontWeight: 700 }}>A. Location-Estimated</div>
                <div style={{ fontSize: '10px', opacity: 0.85 }}>Lower confidence; unmeasured</div>
              </div>
            </button>

            <button
              type="button"
              className={`btn btn-sm ${soilMode === 'measured' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ fontSize: '11.5px', justifyContent: 'flex-start', textAlign: 'left', padding: '8px 10px' }}
              onClick={() => setSoilMode('measured')}
            >
              <div>
                <div style={{ fontWeight: 700 }}>B. Soil Health Card</div>
                <div style={{ fontSize: '10px', opacity: 0.85 }}>Measured NPK; high confidence</div>
              </div>
            </button>

            <button
              type="button"
              className={`btn btn-sm ${soilMode === 'manual' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ fontSize: '11.5px', justifyContent: 'flex-start', textAlign: 'left', padding: '8px 10px' }}
              onClick={() => setSoilMode('manual')}
            >
              <div>
                <div style={{ fontWeight: 700 }}>C. Manual Soil Texture</div>
                <div style={{ fontSize: '10px', opacity: 0.85 }}>Regional texture profile</div>
              </div>
            </button>

            <button
              type="button"
              className={`btn btn-sm ${soilMode === 'report' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ fontSize: '11.5px', justifyContent: 'flex-start', textAlign: 'left', padding: '8px 10px' }}
              onClick={() => setSoilMode('report')}
            >
              <div>
                <div style={{ fontWeight: 700 }}>D. Soil Report Upload</div>
                <div style={{ fontSize: '10px', opacity: 0.85 }}>Document stored; extraction pending</div>
              </div>
            </button>
          </div>

          {/* Conditional Mode Content: Mode A (Location-Estimated) */}
          {soilMode === 'automatic' && (
            <div style={{ padding: '10px 12px', background: 'var(--bg-surface-soft)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
              Regional soil profile derived automatically from your farm location. Measured NPK remains unforced to prevent erroneous dosage claims.
            </div>
          )}

          {/* Conditional Mode Content: Mode B (Soil Health Card - Aligned 3-Column NPK Grid) */}
          {soilMode === 'measured' && (
            <div className="npk-grid">
              <div className="npk-field">
                <div className="npk-label-group">
                  <span className="npk-name">Nitrogen (N)</span>
                  <span className="npk-unit">kg/ha</span>
                </div>
                <input
                  type="number"
                  className="input npk-input"
                  placeholder="e.g. 20"
                  value={n}
                  onChange={e => setN(e.target.value)}
                  min="0"
                />
              </div>

              <div className="npk-field">
                <div className="npk-label-group">
                  <span className="npk-name">Phosphorus (P)</span>
                  <span className="npk-unit">kg/ha</span>
                </div>
                <input
                  type="number"
                  className="input npk-input"
                  placeholder="e.g. 45"
                  value={p}
                  onChange={e => setP(e.target.value)}
                  min="0"
                />
              </div>

              <div className="npk-field">
                <div className="npk-label-group">
                  <span className="npk-name">Potassium (K)</span>
                  <span className="npk-unit">kg/ha</span>
                </div>
                <input
                  type="number"
                  className="input npk-input"
                  placeholder="e.g. 70"
                  value={k}
                  onChange={e => setK(e.target.value)}
                  min="0"
                />
              </div>
            </div>
          )}

          {/* Conditional Mode Content: Mode C (Manual Soil Texture) */}
          {soilMode === 'manual' && (
            <div style={{ marginTop: '8px' }}>
              <label className="form-label">Select Soil Texture Type</label>
              <select className="select" value={soilType} onChange={e => setSoilType(e.target.value)}>
                {SOIL_TYPES.map(st => (
                  <option key={st} value={st}>{st}</option>
                ))}
              </select>
            </div>
          )}

          {/* Conditional Mode Content: Mode D (Soil Report Upload) */}
          {soilMode === 'report' && (
            <div style={{ marginTop: '4px' }}>
              {!soilReportFile ? (
                <div
                  className={`soil-report-dropzone ${soilReportDragOver ? 'dragover' : ''}`}
                  onDragOver={e => {
                    e.preventDefault();
                    setSoilReportDragOver(true);
                  }}
                  onDragLeave={() => setSoilReportDragOver(false)}
                  onDrop={e => {
                    e.preventDefault();
                    setSoilReportDragOver(false);
                    const file = e.dataTransfer.files?.[0];
                    if (file) handleSoilReportChange(file);
                  }}
                  onClick={() => soilReportInputRef.current?.click()}
                >
                  <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'var(--forest-tint)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--forest-dark)' }}>
                    <Upload size={20} />
                  </div>
                  <div>
                    <strong style={{ fontSize: '13.5px', color: 'var(--text-primary)', display: 'block' }}>
                      Upload Soil Report
                    </strong>
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginTop: '2px' }}>
                      Drag and drop your soil report here, or click to browse
                    </span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginTop: '4px' }}>
                      Accepted formats: PDF, JPG, JPEG, PNG
                    </span>
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: 1.4, maxWidth: '340px' }}>
                    Upload a Soil Health Card or laboratory soil report containing available nutrient measurements.
                  </p>
                  <input
                    ref={soilReportInputRef}
                    type="file"
                    accept=".pdf,application/pdf,image/jpeg,image/png,image/webp"
                    style={{ display: 'none' }}
                    onChange={e => handleSoilReportChange(e.target.files?.[0] || null)}
                  />
                </div>
              ) : (
                <div className="soil-report-dropzone has-file">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: '12px', textAlign: 'left' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                      <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-xs)', background: 'var(--bg-surface)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--forest-primary)', flexShrink: 0 }}>
                        <FileCheck size={18} />
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          ✓ {soilReportFile.name}
                        </div>
                        <div style={{ fontSize: '11.5px', color: '#b45309', marginTop: '2px', fontWeight: 600 }}>
                          {soilReportFile.name.split('.').pop()?.toUpperCase() || 'FILE'} · {formatFileSize(soilReportFile.size)} · State: Uploaded (Extraction Pending) — NPK remains unmeasured
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSoilReportChange(null);
                      }}
                      className="btn btn-secondary btn-sm"
                      style={{ padding: '4px 10px', fontSize: '11px', flexShrink: 0 }}
                    >
                      <X size={12} />
                      <span>Remove</span>
                    </button>
                  </div>
                </div>
              )}

              <div style={{ marginTop: '8px', padding: '10px 12px', background: 'var(--bg-surface-soft)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '11.5px', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                <strong>Note on Report Processing:</strong> Automated OCR lab extraction is currently in preview; file is stored for your field advisory record. To calculate exact nutrient deficiency and receive dosage guidance today, please input values directly via <strong>Mode B (Soil Health Card)</strong>.
              </div>
            </div>
          )}
        </div>

        {/* ---------------- SECTION 3: CROP DISEASE PHOTO (Section 25) ---------------- */}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ImageIcon size={16} color="var(--forest-primary)" />
              <h3 style={{ fontSize: '14px', fontWeight: 700, margin: 0 }}>3. Crop Leaf Photograph [Optional]</h3>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>JPG, PNG or WebP</span>
          </div>

          <div
            style={{
              border: '2px dashed var(--border-color)',
              borderRadius: 'var(--radius-md)',
              padding: '16px',
              textAlign: 'center',
              background: image ? 'var(--forest-tint)' : 'var(--bg-surface-soft)',
              transition: 'all 0.2s ease',
              position: 'relative',
            }}
          >
            {imagePreview ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '14px' }}>
                <img
                  src={imagePreview}
                  alt="Crop leaf preview"
                  style={{ width: '64px', height: '64px', objectFit: 'cover', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}
                />
                <div style={{ textAlign: 'left' }}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>{image?.name}</div>
                  <div style={{ fontSize: '11.5px', color: 'var(--forest-dark)' }}>
                    Ready for {diseaseModel === 'dinov2_lora' ? 'DINOv2-Small Rank-4 LoRA' : 'PyTorch MobileNet'} inference
                  </div>
                  <button
                    type="button"
                    onClick={() => handleImageChange(null)}
                    style={{ background: 'none', border: 'none', color: 'var(--semantic-danger)', fontSize: '11px', fontWeight: 600, cursor: 'pointer', padding: 0, marginTop: '4px' }}
                  >
                    ✕ Remove image
                  </button>
                </div>
              </div>
            ) : (
              <div>
                <Upload size={22} color="var(--forest-primary)" style={{ margin: '0 auto 6px' }} />
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Drag and drop leaf photo, or click to browse
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  Leave empty for clean agronomic data-only advisory.
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    opacity: 0,
                    cursor: 'pointer',
                  }}
                  onChange={e => handleImageChange(e.target.files?.[0] || null)}
                />
              </div>
            )}
          </div>

          {/* Disease Vision Model Selection & Optional Crop Condition */}
          <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label className="form-label" style={{ fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
                  Vision Model Architecture
                </label>
                <select
                  className="input"
                  value={diseaseModel}
                  onChange={e => setDiseaseModel(e.target.value as any)}
                  style={{ fontSize: '12px', padding: '6px 8px' }}
                >
                  <option value="dinov2_lora">DINOv2-Small Rank-4 LoRA (Default)</option>
                  <option value="production">MobileNetV3 (Rollback Baseline)</option>
                </select>
              </div>

              <div>
                <label className="form-label" style={{ fontSize: '11px', fontWeight: 600, marginBottom: '4px' }}>
                  Optional Diagnostic Crop Filter
                </label>
                <select
                  className="input"
                  value={leafCropSelection}
                  onChange={e => setLeafCropSelection(e.target.value)}
                  style={{ fontSize: '12px', padding: '6px 8px' }}
                >
                  <option value="none">Unconstrained (All 38 Classes) - Default</option>
                  <option value="auto">Auto (Match Farm Crop: {crop})</option>
                  <option value="Tomato">Tomato (10 classes)</option>
                  <option value="Potato">Potato (3 classes)</option>
                  <option value="Corn">Corn / Maize (4 classes)</option>
                  <option value="Apple">Apple (4 classes)</option>
                  <option value="Grape">Grape (4 classes)</option>
                  <option value="Pepper">Pepper (2 classes)</option>
                  <option value="Cherry">Cherry (2 classes)</option>
                  <option value="Peach">Peach (2 classes)</option>
                  <option value="Strawberry">Strawberry (2 classes)</option>
                  <option value="Squash">Squash (1 class)</option>
                  <option value="Soybean">Soybean (1 class)</option>
                  <option value="Orange">Orange / Citrus (1 class)</option>
                  <option value="Blueberry">Blueberry (1 class)</option>
                  <option value="Raspberry">Raspberry (1 class)</option>
                </select>
              </div>
            </div>

            <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.35 }}>
              <strong>Crop-Aware Conditioning:</strong> When supplied, probabilities are conditioned on the specified species while cross-crop safety safeguards prevent forced misdiagnosis if visual symptoms diverge.
            </div>
          </div>
        </div>

        {/* ---------------- SECTION 4: MARKET BENCHMARK [Optional] ---------------- */}
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div>
              <label className="form-label" style={{ fontSize: '11.5px' }}>
                Mandi Benchmark Price (₹/q) [Optional]
              </label>
              <input
                className="input"
                placeholder="e.g. 2200"
                value={currentPrice}
                onChange={e => setCurrentPrice(e.target.value)}
              />
            </div>
            <div>
              <label className="form-label" style={{ fontSize: '11.5px' }}>
                Price Trend (comma-separated) [Optional]
              </label>
              <input
                className="input"
                placeholder="e.g. 2000,2100,2200"
                value={priceHistory}
                onChange={e => setPriceHistory(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Submit Execution Button */}
        <button
          type="submit"
          disabled={loading}
          className="btn btn-primary"
          style={{ width: '100%', padding: '12px 18px', fontSize: '14px', marginTop: '6px' }}
        >
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div className="spinner" style={{ width: '16px', height: '16px' }} />
              <span>Orchestrating Specialist Agents…</span>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sprout size={16} />
              <span>Run AgriMind Crop Advisory</span>
            </div>
          )}
        </button>

        {error && (
          <div style={{ padding: '10px 12px', background: 'var(--semantic-danger-bg)', border: '1px solid var(--semantic-danger-border)', borderRadius: 'var(--radius-sm)', color: 'var(--semantic-danger-text)', fontSize: '12.5px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}
      </form>
    </div>
  );
}
