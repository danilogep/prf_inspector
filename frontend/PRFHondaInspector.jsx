import React, { useState, useRef, useCallback } from 'react';
import { Camera, Upload, CheckCircle, XCircle, AlertTriangle, Shield, History, BarChart3, ChevronRight, Loader2, ThumbsUp, ThumbsDown, Star } from 'lucide-react';

// Cores PRF
const colors = {
  primary: '#0D1B4C',      // Azul escuro PRF
  secondary: '#1E3A8A',    // Azul médio
  accent: '#F59E0B',       // Amarelo/Dourado
  success: '#10B981',      // Verde
  danger: '#EF4444',       // Vermelho
  warning: '#F97316',      // Laranja
  light: '#F8FAFC',
  white: '#FFFFFF',
  gray: '#64748B',
  darkGray: '#1E293B'
};

export default function PRFHondaInspector() {
  const [currentView, setCurrentView] = useState('home');
  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [year, setYear] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const fileInputRef = useRef(null);
  
  const API_URL = 'http://localhost:8000';

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedImage(file);
      const reader = new FileReader();
      reader.onloadend = () => setImagePreview(reader.result);
      reader.readAsDataURL(file);
    }
  };

  const analyzeMotor = async () => {
    if (!selectedImage || !year) return;
    
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('photo', selectedImage);
      formData.append('year', year);
      
      const response = await fetch(`${API_URL}/analyze/motor`, {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      setResult(data);
      setCurrentView('result');
    } catch (error) {
      alert('Erro ao analisar: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const evaluateAnalysis = async (correct, isFraud) => {
    const analysisId = result?.components?.analysis_id;
    if (!analysisId) return;
    
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('correct', correct);
      if (isFraud !== null) formData.append('is_fraud', isFraud);
      
      await fetch(`${API_URL}/evaluate/${analysisId}`, {
        method: 'POST',
        body: formData
      });
      
      alert('Avaliação salva com sucesso!');
    } catch (error) {
      alert('Erro: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    try {
      const response = await fetch(`${API_URL}/history?limit=20`);
      const data = await response.json();
      setHistory(data.analyses || []);
      setCurrentView('history');
    } catch (error) {
      alert('Erro ao carregar histórico');
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch(`${API_URL}/stats`);
      const data = await response.json();
      setStats(data);
      setCurrentView('stats');
    } catch (error) {
      alert('Erro ao carregar estatísticas');
    }
  };

  const resetAnalysis = () => {
    setSelectedImage(null);
    setImagePreview(null);
    setYear('');
    setResult(null);
    setCurrentView('home');
  };

  const getVerdictStyle = (verdict) => {
    if (!verdict) return { bg: colors.gray, icon: AlertTriangle };
    const v = verdict.toUpperCase();
    if (v.includes('FRAUDE') || v.includes('ALTA')) return { bg: colors.danger, icon: XCircle };
    if (v.includes('SUSPEITO') || v.includes('ATENÇÃO')) return { bg: colors.warning, icon: AlertTriangle };
    return { bg: colors.success, icon: CheckCircle };
  };

  // Componente Header
  const Header = () => (
    <div style={{
      background: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.secondary} 100%)`,
      padding: '16px 20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <Shield size={32} color={colors.accent} strokeWidth={2.5} />
        <div>
          <h1 style={{ 
            color: colors.white, 
            fontSize: '18px', 
            fontWeight: '700',
            letterSpacing: '0.5px',
            margin: 0
          }}>
            PRF INSPECTOR
          </h1>
          <p style={{ 
            color: colors.accent, 
            fontSize: '11px',
            fontWeight: '600',
            letterSpacing: '2px',
            margin: 0
          }}>
            ANÁLISE DE MOTORES HONDA
          </p>
        </div>
      </div>
      <div style={{
        background: colors.accent,
        padding: '4px 10px',
        borderRadius: '12px',
        fontSize: '10px',
        fontWeight: '700',
        color: colors.primary
      }}>
        v5.2
      </div>
    </div>
  );

  // Tela Home
  const HomeView = () => (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Upload Area */}
      <div 
        onClick={() => fileInputRef.current?.click()}
        style={{
          background: imagePreview ? 'transparent' : `linear-gradient(135deg, ${colors.light} 0%, #E2E8F0 100%)`,
          border: `3px dashed ${imagePreview ? colors.success : colors.secondary}`,
          borderRadius: '20px',
          padding: imagePreview ? '0' : '40px 20px',
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'all 0.3s ease',
          overflow: 'hidden',
          position: 'relative',
          minHeight: '200px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        {imagePreview ? (
          <img 
            src={imagePreview} 
            alt="Preview" 
            style={{ 
              width: '100%', 
              height: '250px', 
              objectFit: 'cover',
              borderRadius: '17px'
            }} 
          />
        ) : (
          <div>
            <div style={{
              width: '80px',
              height: '80px',
              background: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.secondary} 100%)`,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px'
            }}>
              <Camera size={36} color={colors.accent} />
            </div>
            <p style={{ 
              color: colors.primary, 
              fontWeight: '600',
              fontSize: '16px',
              margin: '0 0 8px 0'
            }}>
              Toque para capturar foto
            </p>
            <p style={{ 
              color: colors.gray, 
              fontSize: '13px',
              margin: 0
            }}>
              ou selecionar da galeria
            </p>
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleImageSelect}
          style={{ display: 'none' }}
        />
      </div>

      {/* Ano Input */}
      <div style={{
        background: colors.white,
        borderRadius: '16px',
        padding: '16px 20px',
        boxShadow: '0 4px 15px rgba(0,0,0,0.08)'
      }}>
        <label style={{ 
          color: colors.primary, 
          fontWeight: '600',
          fontSize: '14px',
          display: 'block',
          marginBottom: '10px'
        }}>
          Ano do Veículo
        </label>
        <input
          type="number"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          placeholder="Ex: 2015"
          style={{
            width: '100%',
            padding: '14px 16px',
            fontSize: '18px',
            fontWeight: '600',
            border: `2px solid ${colors.light}`,
            borderRadius: '12px',
            outline: 'none',
            transition: 'border-color 0.3s',
            boxSizing: 'border-box'
          }}
          onFocus={(e) => e.target.style.borderColor = colors.accent}
          onBlur={(e) => e.target.style.borderColor = colors.light}
        />
        <p style={{ 
          color: colors.gray, 
          fontSize: '12px',
          marginTop: '8px',
          margin: '8px 0 0 0'
        }}>
          {year && parseInt(year) < 2010 
            ? '⚙️ Esperado: ESTAMPAGEM' 
            : year && parseInt(year) >= 2010 
            ? '🔦 Esperado: LASER'
            : 'Informe o ano para validação'}
        </p>
      </div>

      {/* Botão Analisar */}
      <button
        onClick={analyzeMotor}
        disabled={!selectedImage || !year || loading}
        style={{
          background: selectedImage && year 
            ? `linear-gradient(135deg, ${colors.primary} 0%, ${colors.secondary} 100%)`
            : colors.gray,
          color: colors.white,
          border: 'none',
          borderRadius: '16px',
          padding: '18px',
          fontSize: '16px',
          fontWeight: '700',
          cursor: selectedImage && year ? 'pointer' : 'not-allowed',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '10px',
          boxShadow: selectedImage && year ? '0 8px 25px rgba(13,27,76,0.3)' : 'none',
          transition: 'all 0.3s ease'
        }}
      >
        {loading ? (
          <>
            <Loader2 size={22} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
            ANALISANDO...
          </>
        ) : (
          <>
            <Shield size={22} />
            ANALISAR MOTOR
          </>
        )}
      </button>

      {/* Menu Inferior */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '12px',
        marginTop: '10px'
      }}>
        <button
          onClick={loadHistory}
          style={{
            background: colors.white,
            border: `2px solid ${colors.light}`,
            borderRadius: '14px',
            padding: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            cursor: 'pointer'
          }}
        >
          <History size={20} color={colors.primary} />
          <span style={{ color: colors.primary, fontWeight: '600', fontSize: '14px' }}>
            Histórico
          </span>
        </button>
        <button
          onClick={loadStats}
          style={{
            background: colors.white,
            border: `2px solid ${colors.light}`,
            borderRadius: '14px',
            padding: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            cursor: 'pointer'
          }}
        >
          <BarChart3 size={20} color={colors.primary} />
          <span style={{ color: colors.primary, fontWeight: '600', fontSize: '14px' }}>
            Estatísticas
          </span>
        </button>
      </div>
    </div>
  );

  // Tela Resultado
  const ResultView = () => {
    const verdictStyle = getVerdictStyle(result?.verdict);
    const VerdictIcon = verdictStyle.icon;
    
    return (
      <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Card Veredito */}
        <div style={{
          background: verdictStyle.bg,
          borderRadius: '20px',
          padding: '24px',
          textAlign: 'center',
          boxShadow: '0 8px 30px rgba(0,0,0,0.2)'
        }}>
          <VerdictIcon size={56} color={colors.white} strokeWidth={2.5} />
          <h2 style={{ 
            color: colors.white, 
            fontSize: '24px',
            fontWeight: '800',
            margin: '12px 0 8px 0',
            letterSpacing: '1px'
          }}>
            {result?.verdict || 'ANALISANDO'}
          </h2>
          <div style={{
            background: 'rgba(255,255,255,0.2)',
            borderRadius: '30px',
            padding: '8px 20px',
            display: 'inline-block'
          }}>
            <span style={{ 
              color: colors.white, 
              fontSize: '14px',
              fontWeight: '600'
            }}>
              Score: {result?.risk_score || 0}/100
            </span>
          </div>
        </div>

        {/* Código Lido */}
        <div style={{
          background: colors.white,
          borderRadius: '16px',
          padding: '20px',
          boxShadow: '0 4px 15px rgba(0,0,0,0.08)'
        }}>
          <p style={{ 
            color: colors.gray, 
            fontSize: '12px',
            fontWeight: '600',
            letterSpacing: '1px',
            margin: '0 0 8px 0'
          }}>
            CÓDIGO IDENTIFICADO
          </p>
          <p style={{ 
            color: colors.primary, 
            fontSize: '28px',
            fontWeight: '800',
            fontFamily: 'monospace',
            letterSpacing: '2px',
            margin: 0
          }}>
            {result?.read_code || 'N/A'}
          </p>
          {result?.expected_model && (
            <p style={{ 
              color: colors.accent, 
              fontSize: '14px',
              fontWeight: '600',
              marginTop: '8px',
              margin: '8px 0 0 0'
            }}>
              {result.expected_model}
            </p>
          )}
        </div>

        {/* Detalhes */}
        <div style={{
          background: colors.white,
          borderRadius: '16px',
          padding: '20px',
          boxShadow: '0 4px 15px rgba(0,0,0,0.08)'
        }}>
          <p style={{ 
            color: colors.gray, 
            fontSize: '12px',
            fontWeight: '600',
            letterSpacing: '1px',
            margin: '0 0 12px 0'
          }}>
            ANÁLISE DETALHADA
          </p>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: colors.gray, fontSize: '14px' }}>Tipo Detectado</span>
              <span style={{ 
                color: colors.primary, 
                fontWeight: '700',
                fontSize: '14px'
              }}>
                {result?.components?.ai_analysis?.detected_type || 'N/A'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: colors.gray, fontSize: '14px' }}>Tipo Esperado</span>
              <span style={{ 
                color: colors.primary, 
                fontWeight: '700',
                fontSize: '14px'
              }}>
                {result?.components?.ai_analysis?.expected_type || 'N/A'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: colors.gray, fontSize: '14px' }}>Mistura de Tipos</span>
              <span style={{ 
                color: result?.components?.ai_analysis?.has_mixed_types ? colors.danger : colors.success, 
                fontWeight: '700',
                fontSize: '14px'
              }}>
                {result?.components?.ai_analysis?.has_mixed_types ? '⚠️ SIM' : '✓ NÃO'}
              </span>
            </div>
          </div>
        </div>

        {/* Alertas */}
        {result?.explanation?.length > 0 && (
          <div style={{
            background: colors.white,
            borderRadius: '16px',
            padding: '20px',
            boxShadow: '0 4px 15px rgba(0,0,0,0.08)'
          }}>
            <p style={{ 
              color: colors.gray, 
              fontSize: '12px',
              fontWeight: '600',
              letterSpacing: '1px',
              margin: '0 0 12px 0'
            }}>
              ALERTAS E OBSERVAÇÕES
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {result.explanation.slice(0, 5).map((item, idx) => (
                <div 
                  key={idx}
                  style={{
                    background: item.includes('🚨') ? '#FEE2E2' : item.includes('⚠️') ? '#FEF3C7' : '#F0FDF4',
                    padding: '10px 12px',
                    borderRadius: '10px',
                    fontSize: '13px',
                    color: colors.darkGray
                  }}
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Avaliação */}
        <div style={{
          background: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.secondary} 100%)`,
          borderRadius: '16px',
          padding: '20px',
          boxShadow: '0 8px 25px rgba(13,27,76,0.3)'
        }}>
          <p style={{ 
            color: colors.accent, 
            fontSize: '12px',
            fontWeight: '600',
            letterSpacing: '1px',
            margin: '0 0 12px 0'
          }}>
            AVALIAR RESULTADO
          </p>
          <p style={{ 
            color: colors.white, 
            fontSize: '14px',
            margin: '0 0 16px 0'
          }}>
            A análise da IA está correta?
          </p>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={() => evaluateAnalysis(true, result?.verdict?.includes('FRAUDE'))}
              disabled={loading}
              style={{
                flex: 1,
                background: colors.success,
                color: colors.white,
                border: 'none',
                borderRadius: '12px',
                padding: '14px',
                fontWeight: '700',
                fontSize: '14px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
            >
              <ThumbsUp size={18} />
              CORRETA
            </button>
            <button
              onClick={() => evaluateAnalysis(false, null)}
              disabled={loading}
              style={{
                flex: 1,
                background: colors.danger,
                color: colors.white,
                border: 'none',
                borderRadius: '12px',
                padding: '14px',
                fontWeight: '700',
                fontSize: '14px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
            >
              <ThumbsDown size={18} />
              INCORRETA
            </button>
          </div>
        </div>

        {/* Botão Nova Análise */}
        <button
          onClick={resetAnalysis}
          style={{
            background: colors.white,
            color: colors.primary,
            border: `2px solid ${colors.primary}`,
            borderRadius: '16px',
            padding: '16px',
            fontSize: '15px',
            fontWeight: '700',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px'
          }}
        >
          <Camera size={20} />
          NOVA ANÁLISE
        </button>
      </div>
    );
  };

  // Tela Histórico
  const HistoryView = () => (
    <div style={{ padding: '20px' }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        marginBottom: '20px'
      }}>
        <h2 style={{ 
          color: colors.primary, 
          fontSize: '20px',
          fontWeight: '700',
          margin: 0
        }}>
          Histórico de Análises
        </h2>
        <button
          onClick={() => setCurrentView('home')}
          style={{
            background: 'none',
            border: 'none',
            color: colors.accent,
            fontWeight: '600',
            cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          Voltar
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {history.length === 0 ? (
          <p style={{ color: colors.gray, textAlign: 'center', padding: '40px' }}>
            Nenhuma análise encontrada
          </p>
        ) : (
          history.map((item, idx) => {
            const style = getVerdictStyle(item.verdict);
            return (
              <div 
                key={idx}
                style={{
                  background: colors.white,
                  borderRadius: '14px',
                  padding: '16px',
                  boxShadow: '0 4px 15px rgba(0,0,0,0.08)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '14px'
                }}
              >
                <div style={{
                  width: '50px',
                  height: '50px',
                  borderRadius: '12px',
                  background: style.bg,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  {React.createElement(style.icon, { size: 24, color: colors.white })}
                </div>
                <div style={{ flex: 1 }}>
                  <p style={{ 
                    color: colors.primary, 
                    fontWeight: '700',
                    fontSize: '16px',
                    fontFamily: 'monospace',
                    margin: '0 0 4px 0'
                  }}>
                    {item.read_code || 'N/A'}
                  </p>
                  <p style={{ 
                    color: colors.gray, 
                    fontSize: '12px',
                    margin: 0
                  }}>
                    {item.year_informed} • Score: {item.risk_score}
                    {item.evaluated && (item.evaluation_correct ? ' ✓' : ' ✗')}
                  </p>
                </div>
                <ChevronRight size={20} color={colors.gray} />
              </div>
            );
          })
        )}
      </div>
    </div>
  );

  // Tela Estatísticas
  const StatsView = () => (
    <div style={{ padding: '20px' }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        marginBottom: '20px'
      }}>
        <h2 style={{ 
          color: colors.primary, 
          fontSize: '20px',
          fontWeight: '700',
          margin: 0
        }}>
          Estatísticas
        </h2>
        <button
          onClick={() => setCurrentView('home')}
          style={{
            background: 'none',
            border: 'none',
            color: colors.accent,
            fontWeight: '600',
            cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          Voltar
        </button>
      </div>

      {stats && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Acurácia */}
          <div style={{
            background: `linear-gradient(135deg, ${colors.primary} 0%, ${colors.secondary} 100%)`,
            borderRadius: '20px',
            padding: '24px',
            textAlign: 'center'
          }}>
            <Star size={40} color={colors.accent} />
            <p style={{ 
              color: colors.accent, 
              fontSize: '48px',
              fontWeight: '800',
              margin: '8px 0'
            }}>
              {stats.accuracy_rate || 0}%
            </p>
            <p style={{ 
              color: colors.white, 
              fontSize: '14px',
              fontWeight: '600',
              margin: 0
            }}>
              Taxa de Acurácia
            </p>
          </div>

          {/* Grid de Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <StatCard label="Total Análises" value={stats.total_analyses || 0} color={colors.primary} />
            <StatCard label="Avaliadas" value={stats.total_evaluated || 0} color={colors.secondary} />
            <StatCard label="Corretas" value={stats.total_correct || 0} color={colors.success} />
            <StatCard label="Pendentes" value={stats.pending_evaluation || 0} color={colors.warning} />
            <StatCard label="Originais" value={stats.originals || 0} color={colors.success} />
            <StatCard label="Fraudes" value={stats.frauds || 0} color={colors.danger} />
          </div>
        </div>
      )}
    </div>
  );

  const StatCard = ({ label, value, color }) => (
    <div style={{
      background: colors.white,
      borderRadius: '14px',
      padding: '20px',
      textAlign: 'center',
      boxShadow: '0 4px 15px rgba(0,0,0,0.08)'
    }}>
      <p style={{ 
        color: color, 
        fontSize: '32px',
        fontWeight: '800',
        margin: '0 0 4px 0'
      }}>
        {value}
      </p>
      <p style={{ 
        color: colors.gray, 
        fontSize: '12px',
        fontWeight: '600',
        margin: 0
      }}>
        {label}
      </p>
    </div>
  );

  return (
    <div style={{
      minHeight: '100vh',
      background: colors.light,
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      <style>
        {`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          * { box-sizing: border-box; }
          input::-webkit-outer-spin-button,
          input::-webkit-inner-spin-button {
            -webkit-appearance: none;
            margin: 0;
          }
        `}
      </style>
      
      <Header />
      
      {currentView === 'home' && <HomeView />}
      {currentView === 'result' && <ResultView />}
      {currentView === 'history' && <HistoryView />}
      {currentView === 'stats' && <StatsView />}
    </div>
  );
}
