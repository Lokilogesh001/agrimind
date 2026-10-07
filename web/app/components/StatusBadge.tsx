'use client';

import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Info,
  ShieldAlert,
  ShieldCheck,
  Clock,
  Sparkles,
} from 'lucide-react';

export type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'brand' | 'mint';

interface StatusBadgeProps {
  label: string;
  variant?: BadgeVariant;
  icon?: 'check' | 'warning' | 'danger' | 'info' | 'shield-alert' | 'shield-check' | 'clock' | 'sparkles' | 'none';
  className?: string;
  size?: 'sm' | 'md';
}

export function StatusBadge({
  label,
  variant = 'neutral',
  icon = 'none',
  className = '',
  size = 'md',
}: StatusBadgeProps) {
  const getIcon = () => {
    const iconSize = size === 'sm' ? 12 : 13;
    switch (icon) {
      case 'check':
        return <CheckCircle2 size={iconSize} />;
      case 'warning':
        return <AlertTriangle size={iconSize} />;
      case 'danger':
        return <AlertCircle size={iconSize} />;
      case 'info':
        return <Info size={iconSize} />;
      case 'shield-alert':
        return <ShieldAlert size={iconSize} />;
      case 'shield-check':
        return <ShieldCheck size={iconSize} />;
      case 'clock':
        return <Clock size={iconSize} />;
      case 'sparkles':
        return <Sparkles size={iconSize} />;
      default:
        return null;
    }
  };

  const sizeStyle = size === 'sm'
    ? { padding: '2px 7px', fontSize: '10.5px' }
    : {};

  return (
    <span
      className={`badge badge-${variant} ${className}`}
      style={sizeStyle}
      role="status"
    >
      {getIcon()}
      <span>{label}</span>
    </span>
  );
}
