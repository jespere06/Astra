import React, { useState } from 'react';

/* ── SVG Icons ────────────────────────────────────────────── */
const Icons = {
  Search: () => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
  ),
  Bolt: () => (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
  ),
  Check: () => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
  ),
  Cache: () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 11-6.219-8.56"/><polyline points="22 2 22 8 16 8"/></svg>
  ),
  Spinner: () => (
    <svg className="wizard-spinner" width="20" height="20" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" opacity=".2"/><path d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" fill="currentColor" opacity=".8"/></svg>
  ),
};

/* ── Badge ────────────────────────────────────────────────── */
function Badge({ text, variant = 'default' }) {
  return (
    <span className={`wizard-badge wizard-badge--${variant}`}>{text}</span>
  );
}

/* ── Main Component ───────────────────────────────────────── */
export function TrainingWizard({ onConfirm, onCancel, loading, hasCachedPreparation = false }) {
  const [mode, setMode] = useState('DATA_PREP_ONLY');

  const options = [
    {
      id: 'DATA_PREP_ONLY',
      icon: <Icons.Search />,
      title: 'Solo Preparación y Validación',
      desc: <>Ejecuta el pipeline de minería (descarga, transcripción, alineación) para generar el dataset y verificar la calidad de los pares <strong>sin gastar créditos de GPU</strong>.</>,
      badges: [
        { text: 'Costo Cero', variant: 'green' },
        { text: 'Rápido (~5m)', variant: 'cyan' },
        { text: 'Genera Reporte', variant: 'muted' },
      ],
      accent: 'cyan',
    },
    {
      id: 'FULL_TRAINING',
      icon: <Icons.Bolt />,
      title: 'Entrenamiento Completo (Fine-Tuning)',
      desc: <>Ejecuta la preparación y luego despacha un trabajo a <strong>RunPod</strong> para entrenar el modelo Llama-3 con los nuevos datos. Ideal para producción.</>,
      badges: [
        { text: 'Usa GPU ($)', variant: 'amber' },
        { text: 'Lento (~30m)', variant: 'amber' },
        { text: 'Genera Modelo Nuevo', variant: 'purple' },
      ],
      accent: 'purple',
    },
  ];

  const selectedAccent = mode === 'DATA_PREP_ONLY' ? 'cyan' : 'purple';

  return (
    <div className="wizard-overlay">
      <div className="wizard-modal" role="dialog" aria-label="Configurar Ejecución">

        {/* Top gradient accent */}
        <div className="wizard-modal__accent" />

        {/* Header */}
        <div className="wizard-header">
          <h3 className="wizard-header__title">Configurar Ejecución</h3>
          <p className="wizard-header__subtitle">Define la estrategia de procesamiento para el lote actual.</p>
        </div>

        {/* Options */}
        <div className="wizard-body">
          {options.map((opt) => {
            const selected = mode === opt.id;
            const showCache = opt.id === 'FULL_TRAINING' && hasCachedPreparation;

            return (
              <button
                key={opt.id}
                type="button"
                className={`wizard-option wizard-option--${opt.accent} ${selected ? 'wizard-option--active' : ''}`}
                onClick={() => setMode(opt.id)}
                aria-pressed={selected}
              >
                {/* Selection indicator */}
                <div className={`wizard-option__radio ${selected ? 'wizard-option__radio--checked' : ''}`}>
                  {selected && <Icons.Check />}
                </div>

                {/* Icon */}
                <div className={`wizard-option__icon wizard-option__icon--${opt.accent} ${selected ? 'wizard-option__icon--active' : ''}`}>
                  {opt.icon}
                </div>

                {/* Content */}
                <div className="wizard-option__content">
                  <div className="wizard-option__title-row">
                    <span className="wizard-option__title">{opt.title}</span>
                    {showCache && (
                      <span className="wizard-cache-badge">
                        <Icons.Cache />
                        Caché disponible — se retomará
                      </span>
                    )}
                  </div>
                  <p className="wizard-option__desc">{opt.desc}</p>
                  <div className="wizard-option__badges">
                    {opt.badges.map((b, i) => <Badge key={i} text={b.text} variant={b.variant} />)}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Footer */}
        <div className="wizard-footer">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={onCancel}
            disabled={loading}
          >
            Cancelar
          </button>

          <button
            type="button"
            className={`wizard-footer__submit wizard-footer__submit--${selectedAccent}`}
            onClick={() => onConfirm(mode)}
            disabled={loading}
          >
            {loading ? (
              <>
                <Icons.Spinner />
                <span>Procesando…</span>
              </>
            ) : (
              <>
                <span>{mode === 'DATA_PREP_ONLY' ? 'Ejecutar Análisis' : 'Iniciar Entrenamiento'}</span>
                <span className="wizard-footer__arrow">→</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}