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
  Tag,
  Check,
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
  // Model Selection & Leaf Crop Conditioning (DINOv2 LoRA is the active default)
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
  const [growthStage, setGrowthStage] = useState('flowering');

  // Soil Mode
  const [soilMode, setSoilMode] = useState<'automatic' | 'manual' | 'measured' | 'report'>('measured');
  const [soilType, setSoilType] = useState('Red Soil');
  const [n, setN] = useState('180');
  const [p, setP] = useState('24');
  const [k, setK] = useState('190');

  // Soil Report File State (Mode D)
  const [soilReportFile, setSoilReportFile] = useState<File | null>(null);
  const [soilReportDragOver, setSoilReportDragOver] = useState(false);
  const soilReportInputRef = useRef<HTMLInputElement>(null);

  // Context Fields
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
    <div className="form-workspace-card">
      <div className="card-header" style={{ borderBottom: '1px solid var(--border-color)', padding: '18px 24px' }}>
        <div>
          <span className="eyebrow">FIELD TELEMETRY & SCENARIO CONFIGURATION</span>
          <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '3px 0 0', color: 'var(--text-primary)' }}>
            Farm Parameter Workspace
          </h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <StatusBadge label="HIGH-PRECISION GEOCODING" variant="brand" icon="check" size="sm" />
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Coordinates: {selectedLocation.lat?.toFixed(3)}, {selectedLocation.lon?.toFixed(3)}
          </span>
        </div>
      </div>

      <form onSubmit={handleSubmit} style={{ padding: '24px' }}>
        {/* ========================================================================= */}
        {/* THREE HORIZONTAL COLUMNS GRID                                             */}
        {/* ========================================================================= */}
        <div className="form-horizontal-grid">
          {/* ---------------- COLUMN 1: FARM & CROP DETAILS ---------------- */}
          <div className="form-column-card">
            <div className="form-column-header">
              <div className="form-column-title">
                <MapPin size={16} color="var(--teal-accent)" />
                <span>1. Farm & Crop Details</span>
              </div>
              {selectedLocation.name && (
                <span style={{ fontSize: '11px', color: 'var(--teal-accent)', fontWeight: 600 }}>
                  ✓ Geocoded
                </span>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Location Input with Autocomplete */}
              <div style={{ position: 'relative' }}>
                <label className="form-label">
                  <span>Farm Location (Village / District / State)</span>
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
                      background: 'var(--bg-surface-elevated)',
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
                          padding: '10px 14px',
                          borderBottom: '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                          fontSize: '12.5px',
                          transition: 'background-color 0.15s ease',
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

              {/* Crop & Growth Stage Side by Side */}
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

              {/* Farm Area & Irrigation Side by Side */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
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

              {/* Sowing Date [Optional] */}
              <div>
                <label className="form-label">
                  <span>Sowing / Planting Date</span>
                  <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>Optional</span>
                </label>
                <input
                  type="date"
                  className="input"
                  value={sowingDate}
                  onChange={e => setSowingDate(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* ---------------- COLUMN 2: SOIL INFORMATION ---------------- */}
          <div className="form-column-card">
            <div className="form-column-header">
              <div className="form-column-title">
                <FlaskConical size={16} color="var(--teal-accent)" />
                <span>2. Soil Nutrient Method</span>
              </div>
              <span
                style={{
                  fontSize: '10.5px',
                  fontWeight: 700,
                  color: soilMode === 'measured' ? 'var(--semantic-success-text)' : (soilMode === 'report' ? 'var(--semantic-warning-text)' : 'var(--text-muted)'),
                  textTransform: 'uppercase',
                }}
              >
                {soilMode === 'measured' ? 'MEASURED (HIGH)' : (soilMode === 'report' ? 'REPORT ATTACHED' : (soilMode === 'manual' ? 'MANUAL TEXTURE' : 'LOCATION ESTIMATE'))}
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* 2x2 Mode Selector Buttons */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <button
                  type="button"
                  className={`btn-soil-mode ${soilMode === 'automatic' ? 'active' : ''}`}
                  onClick={() => setSoilMode('automatic')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span style={{ fontWeight: 700 }}>A. Estimated</span>
                    {soilMode === 'automatic' && <Check size={13} color="var(--teal-accent)" />}
                  </div>
                  <span style={{ fontSize: '10.5px', opacity: 0.85, marginTop: '2px', display: 'block' }}>
                    Regional location profile
                  </span>
                </button>

                <button
                  type="button"
                  className={`btn-soil-mode ${soilMode === 'measured' ? 'active' : ''}`}
                  onClick={() => setSoilMode('measured')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span style={{ fontWeight: 700 }}>B. Health Card</span>
                    {soilMode === 'measured' && <Check size={13} color="var(--teal-accent)" />}
                  </div>
                  <span style={{ fontSize: '10.5px', opacity: 0.85, marginTop: '2px', display: 'block' }}>
                    Measured NPK nutrients
                  </span>
                </button>

                <button
                  type="button"
                  className={`btn-soil-mode ${soilMode === 'manual' ? 'active' : ''}`}
                  onClick={() => setSoilMode('manual')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span style={{ fontWeight: 700 }}>C. Soil Type</span>
                    {soilMode === 'manual' && <Check size={13} color="var(--teal-accent)" />}
                  </div>
                  <span style={{ fontSize: '10.5px', opacity: 0.85, marginTop: '2px', display: 'block' }}>
                    Texture classification
                  </span>
                </button>

                <button
                  type="button"
                  className={`btn-soil-mode ${soilMode === 'report' ? 'active' : ''}`}
                  onClick={() => setSoilMode('report')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span style={{ fontWeight: 700 }}>D. Report Upload</span>
                    {soilMode === 'report' && <Check size={13} color="var(--teal-accent)" />}
                  </div>
                  <span style={{ fontSize: '10.5px', opacity: 0.85, marginTop: '2px', display: 'block' }}>
                    Soil lab document PDF
                  </span>
                </button>
              </div>

              {/* Mode Specific Body */}
              {soilMode === 'automatic' && (
                <div style={{ padding: '12px 14px', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  Regional soil characteristics derived automatically from geocoded coordinates. NPK values are not synthesized to prevent unverified chemical dosage.
                </div>
              )}

              {soilMode === 'measured' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div className="npk-grid">
                    <div className="npk-field">
                      <div className="npk-label-group">
                        <span className="npk-name">Nitrogen (N)</span>
                        <span className="npk-unit">kg/ha</span>
                      </div>
                      <input
                        type="number"
                        className="input npk-input"
                        placeholder="e.g. 180"
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
                        placeholder="e.g. 24"
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
                        placeholder="e.g. 190"
                        value={k}
                        onChange={e => setK(e.target.value)}
                        min="0"
                      />
                    </div>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Enter values from your soil health card or certified laboratory report.
                  </span>
                </div>
              )}

              {soilMode === 'manual' && (
                <div>
                  <label className="form-label">Select Regional Soil Texture</label>
                  <select className="select" value={soilType} onChange={e => setSoilType(e.target.value)}>
                    {SOIL_TYPES.map(st => (
                      <option key={st} value={st}>{st}</option>
                    ))}
                  </select>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginTop: '6px' }}>
                    Used for drainage capacity and retention timing calculations.
                  </span>
                </div>
              )}

              {soilMode === 'report' && (
                <div>
                  {!soilReportFile ? (
                    <div
                      className={`soil-report-dropzone ${soilReportDragOver ? 'dragover' : ''}`}
                      style={{ padding: '16px' }}
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
                      <Upload size={20} color="var(--teal-accent)" />
                      <div style={{ textAlign: 'center' }}>
                        <strong style={{ fontSize: '12.5px', color: 'var(--text-primary)', display: 'block' }}>
                          Upload Soil Test Report
                        </strong>
                        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                          PDF, JPG, PNG accepted (Stored for field record)
                        </span>
                      </div>
                      <input
                        ref={soilReportInputRef}
                        type="file"
                        accept=".pdf,application/pdf,image/jpeg,image/png,image/webp"
                        style={{ display: 'none' }}
                        onChange={e => handleSoilReportChange(e.target.files?.[0] || null)}
                      />
                    </div>
                  ) : (
                    <div className="soil-report-dropzone has-file" style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: '10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                          <FileCheck size={18} color="var(--teal-accent)" style={{ flexShrink: 0 }} />
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              ✓ {soilReportFile.name}
                            </div>
                            <div style={{ fontSize: '10.5px', color: 'var(--semantic-warning-text)' }}>
                              {formatFileSize(soilReportFile.size)} · Extraction Pending
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
                          style={{ padding: '3px 8px', fontSize: '10.5px', flexShrink: 0 }}
                        >
                          <X size={11} />
                          <span>Remove</span>
                        </button>
                      </div>
                    </div>
                  )}
                  <span style={{ fontSize: '10.5px', color: 'var(--text-muted)', display: 'block', marginTop: '6px', lineHeight: 1.4 }}>
                    To receive immediate NPK dosage analysis today, select <strong>Mode B (Health Card)</strong>.
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* ---------------- COLUMN 3: DISEASE DETECTION ---------------- */}
          <div className="form-column-card form-col-disease">
            <div className="form-column-header">
              <div className="form-column-title">
                <ImageIcon size={16} color="var(--teal-accent)" />
                <span>3. Disease Vision Telemetry</span>
              </div>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Optional</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Compact Leaf Image Dropzone */}
              <div
                style={{
                  border: '1.5px dashed var(--border-color)',
                  borderRadius: 'var(--radius-md)',
                  padding: imagePreview ? '12px 16px' : '16px 14px',
                  textAlign: 'center',
                  background: image ? 'var(--forest-tint)' : 'var(--bg-surface-elevated)',
                  position: 'relative',
                  transition: 'all 0.2s ease',
                }}
              >
                {imagePreview ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <img
                      src={imagePreview}
                      alt="Crop leaf preview"
                      style={{ width: '54px', height: '54px', objectFit: 'cover', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-strong)', flexShrink: 0 }}
                    />
                    <div style={{ textAlign: 'left', minWidth: 0, flex: 1 }}>
                      <div style={{ fontSize: '12.5px', fontWeight: 700, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {image?.name}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--teal-accent)', marginTop: '2px' }}>
                        ✓ Ready for {diseaseModel === 'dinov2_lora' ? 'DINOv2 LoRA' : 'MobileNetV3'} inference
                      </div>
                      <button
                        type="button"
                        onClick={() => handleImageChange(null)}
                        style={{ background: 'none', border: 'none', color: 'var(--semantic-danger-text)', fontSize: '11px', fontWeight: 600, cursor: 'pointer', padding: 0, marginTop: '4px' }}
                      >
                        ✕ Remove image
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <Upload size={22} color="var(--teal-accent)" style={{ margin: '0 auto 6px' }} />
                    <div style={{ fontSize: '12.5px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      Drag and drop leaf photo, or click to browse
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      JPG, PNG, WebP · Max 5MB (Optional)
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

              {/* Vision Model Architecture & Diagnostic Crop Filter */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label className="form-label" style={{ fontSize: '11px' }}>
                    Model Architecture
                  </label>
                  <select
                    className="select"
                    value={diseaseModel}
                    onChange={e => setDiseaseModel(e.target.value as any)}
                    style={{ fontSize: '11.5px', padding: '6px 8px' }}
                  >
                    <option value="dinov2_lora">DINOv2-Small LoRA (Default)</option>
                    <option value="production">MobileNetV3 (Baseline)</option>
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontSize: '11px' }}>
                    Crop Conditioning Filter
                  </label>
                  <select
                    className="select"
                    value={leafCropSelection}
                    onChange={e => setLeafCropSelection(e.target.value)}
                    style={{ fontSize: '11.5px', padding: '6px 8px' }}
                  >
                    <option value="none">Unconstrained (38 Classes)</option>
                    <option value="auto">Auto (Match: {crop})</option>
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

              <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                <strong>Crop-Aware Conditioning:</strong> Probabilities are conditioned on the specified species with cross-crop safety safeguards preventing forced misdiagnosis.
              </div>
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* FULL-WIDTH MARKET ROW                                                     */}
        {/* ========================================================================= */}
        <div className="form-market-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <Tag size={15} color="var(--teal-accent)" />
            <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
              4. Mandi Economics & Market Price Benchmarking [Optional]
            </span>
          </div>

          <div className="form-market-grid">
            <div>
              <label className="form-label" style={{ fontSize: '11.5px' }}>
                <span>Mandi Benchmark Price (₹/quintal)</span>
                <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>Optional</span>
              </label>
              <input
                className="input"
                placeholder="e.g. 2000"
                value={currentPrice}
                onChange={e => setCurrentPrice(e.target.value)}
              />
            </div>

            <div>
              <label className="form-label" style={{ fontSize: '11.5px' }}>
                <span>Historical Price Trend (comma-separated ₹/q)</span>
                <span style={{ fontSize: '10.5px', color: 'var(--text-muted)' }}>Optional</span>
              </label>
              <input
                className="input"
                placeholder="e.g. 1950,1980,2000"
                value={priceHistory}
                onChange={e => setPriceHistory(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* FULL-WIDTH PRIMARY ACTION ROW                                             */}
        {/* ========================================================================= */}
        <div className="form-action-row">
          <button
            type="submit"
            disabled={loading}
            className="btn-run-advisory"
            id="btn-run-advisory-primary"
          >
            {loading ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div className="spinner" style={{ width: '18px', height: '18px' }} />
                <span>Orchestrating Autonomous Specialist Cluster…</span>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Sprout size={19} />
                <span>Run AgriMind Crop Advisory</span>
              </div>
            )}
          </button>

          {error && (
            <div style={{ padding: '12px 16px', background: 'var(--semantic-danger-bg)', border: '1px solid var(--semantic-danger-border)', borderRadius: 'var(--radius-sm)', color: 'var(--semantic-danger-text)', fontSize: '12.5px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}
        </div>
      </form>
    </div>
  );
}
