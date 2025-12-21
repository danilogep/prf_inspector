import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  Button, 
  Image, 
  ActivityIndicator, 
  Alert, 
  TextInput, 
  ScrollView, 
  TouchableOpacity 
} from 'react-native';
import { Camera } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';

// ⚠️ ALTERE PARA O IP DO SEU COMPUTADOR
// Use 'ipconfig' (Windows) ou 'ip addr' (Linux) para descobrir
const API_URL = 'http://SEU_IP_AQUI:8000/analyze/motor';

interface AnalysisResult {
  verdict: string;
  risk_score: number;
  read_code: string;
  prefix: string | null;
  serial: string | null;
  expected_model: string | null;
  explanation: string[];
}

export default function App() {
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [image, setImage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  
  // Estado do Formulário
  const [year, setYear] = useState('2020');
  const [model, setModel] = useState('');

  useEffect(() => {
    (async () => {
      const { status } = await Camera.requestCameraPermissionsAsync();
      setHasPermission(status === 'granted');
    })();
  }, []);

  const takePicture = async () => {
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 1,
      base64: false,
    });

    if (!result.canceled) {
      setImage(result.assets[0].uri);
      setResult(null);
    }
  };

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 1,
    });

    if (!result.canceled) {
      setImage(result.assets[0].uri);
      setResult(null);
    }
  };

  const analyzeImage = async () => {
    if (!image) {
      Alert.alert("Erro", "Tire ou selecione uma foto primeiro");
      return;
    }

    setLoading(true);
    const formData = new FormData();
    
    formData.append('photo', {
      uri: image,
      name: 'motor.jpg',
      type: 'image/jpeg',
    } as any);

    formData.append('year', year);
    if (model.trim()) {
      formData.append('model', model.trim());
    }

    try {
      const response = await axios.post(API_URL, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000
      });
      setResult(response.data);
    } catch (error: any) {
      console.error(error);
      if (error.code === 'ECONNABORTED') {
        Alert.alert("Timeout", "A análise demorou muito. Tente novamente.");
      } else if (error.response) {
        Alert.alert("Erro", `Erro do servidor: ${error.response.data?.detail || 'Desconhecido'}`);
      } else {
        Alert.alert("Erro de Conexão", "Verifique se o backend está rodando e se o IP está correto.");
      }
    } finally {
      setLoading(false);
    }
  };

  const getVerdictColor = (verdict: string) => {
    switch (verdict) {
      case 'REGULAR': return '#28a745';
      case 'ATENÇÃO': return '#ffc107';
      case 'SUSPEITO': return '#fd7e14';
      case 'ALTA SUSPEITA DE FRAUDE': return '#dc3545';
      default: return '#6c757d';
    }
  };

  const getVerdictBgColor = (verdict: string) => {
    switch (verdict) {
      case 'REGULAR': return '#d4edda';
      case 'ATENÇÃO': return '#fff3cd';
      case 'SUSPEITO': return '#ffe5d0';
      case 'ALTA SUSPEITA DE FRAUDE': return '#f8d7da';
      default: return '#e2e3e5';
    }
  };

  if (hasPermission === null) {
    return <View style={styles.container}><Text>Solicitando permissão...</Text></View>;
  }
  if (hasPermission === false) {
    return <View style={styles.container}><Text>Sem acesso à câmera</Text></View>;
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>🔍 PRF Honda Inspector</Text>
      <Text style={styles.subtitle}>Análise de Motor</Text>

      {/* Formulário */}
      <View style={styles.card}>
        <Text style={styles.label}>Ano do Modelo:</Text>
        <TextInput 
          style={styles.input} 
          keyboardType='numeric' 
          value={year} 
          onChangeText={setYear}
          placeholder="Ex: 2020"
        />
        
        <Text style={styles.label}>Modelo (opcional):</Text>
        <TextInput 
          style={styles.input} 
          value={model} 
          onChangeText={setModel}
          placeholder="Ex: CG 160, XRE 300"
        />
      </View>

      {/* Botões de Captura */}
      <View style={styles.buttonRow}>
        <TouchableOpacity style={styles.btnCapture} onPress={takePicture}>
          <Text style={styles.btnCaptureText}>📷 Tirar Foto</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.btnGallery} onPress={pickImage}>
          <Text style={styles.btnGalleryText}>🖼️ Galeria</Text>
        </TouchableOpacity>
      </View>

      {/* Preview da Imagem */}
      {image && (
        <View style={styles.previewContainer}>
          <Image source={{ uri: image }} style={styles.preview} />
          
          {loading ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="large" color="#003366" />
              <Text style={styles.loadingText}>Analisando...</Text>
            </View>
          ) : (
            <TouchableOpacity style={styles.btnAnalyze} onPress={analyzeImage}>
              <Text style={styles.btnAnalyzeText}>🔍 ANALISAR MOTOR</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {/* Resultado */}
      {result && (
        <View style={[styles.resultBox, { backgroundColor: getVerdictBgColor(result.verdict) }]}>
          <Text style={[styles.verdictTitle, { color: getVerdictColor(result.verdict) }]}>
            {result.verdict}
          </Text>
          
          <View style={styles.scoreContainer}>
            <Text style={styles.scoreLabel}>Risco:</Text>
            <Text style={[styles.scoreValue, { color: getVerdictColor(result.verdict) }]}>
              {result.risk_score}%
            </Text>
          </View>
          
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Código Lido:</Text>
            <Text style={styles.infoValue}>{result.read_code || 'N/A'}</Text>
          </View>
          
          {result.prefix && (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Prefixo:</Text>
              <Text style={styles.infoValue}>{result.prefix}</Text>
            </View>
          )}
          
          {result.serial && (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Serial:</Text>
              <Text style={styles.infoValue}>{result.serial}</Text>
            </View>
          )}
          
          {result.expected_model && (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Modelo Esperado:</Text>
              <Text style={styles.infoValue}>{result.expected_model}</Text>
            </View>
          )}
          
          {result.explanation && result.explanation.length > 0 && (
            <>
              <Text style={styles.sectionHeader}>Observações:</Text>
              {result.explanation.map((item, index) => (
                <Text key={index} style={styles.reason}>
                  {item.includes('⚠️') ? item : `• ${item}`}
                </Text>
              ))}
            </>
          )}
        </View>
      )}

      {/* Dicas */}
      <View style={styles.tipsCard}>
        <Text style={styles.tipsTitle}>💡 Dicas para melhor análise:</Text>
        <Text style={styles.tipItem}>• Foto nítida e na horizontal</Text>
        <Text style={styles.tipItem}>• Boa iluminação, sem sombras</Text>
        <Text style={styles.tipItem}>• Número do motor ocupando boa parte da imagem</Text>
        <Text style={styles.tipItem}>• Caracteres de alto risco: 0, 1, 3, 4, 9</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { 
    flexGrow: 1, 
    padding: 20, 
    paddingTop: 50, 
    backgroundColor: '#f0f2f5' 
  },
  title: { 
    fontSize: 26, 
    fontWeight: 'bold', 
    textAlign: 'center', 
    color: '#003366' 
  },
  subtitle: {
    fontSize: 16,
    textAlign: 'center',
    color: '#666',
    marginBottom: 20
  },
  card: { 
    backgroundColor: '#fff', 
    padding: 15, 
    borderRadius: 10, 
    marginBottom: 15, 
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  label: { 
    fontWeight: 'bold', 
    marginBottom: 5,
    color: '#333'
  },
  input: { 
    borderWidth: 1, 
    borderColor: '#ddd', 
    padding: 12, 
    marginBottom: 12, 
    borderRadius: 8, 
    backgroundColor: '#fafafa',
    fontSize: 16
  },
  buttonRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 15
  },
  btnCapture: {
    flex: 1,
    backgroundColor: '#003366',
    padding: 15,
    borderRadius: 8,
    marginRight: 8,
    alignItems: 'center'
  },
  btnCaptureText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 16
  },
  btnGallery: {
    flex: 1,
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 8,
    marginLeft: 8,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#003366'
  },
  btnGalleryText: {
    color: '#003366',
    fontWeight: 'bold',
    fontSize: 16
  },
  previewContainer: { 
    alignItems: 'center', 
    marginVertical: 15,
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    elevation: 3
  },
  preview: { 
    width: '100%', 
    height: 180, 
    resizeMode: 'contain', 
    marginBottom: 15, 
    borderRadius: 8,
    backgroundColor: '#f5f5f5'
  },
  loadingContainer: {
    alignItems: 'center',
    padding: 20
  },
  loadingText: {
    marginTop: 10,
    color: '#666',
    fontSize: 16
  },
  btnAnalyze: {
    backgroundColor: '#dc3545',
    paddingVertical: 15,
    paddingHorizontal: 40,
    borderRadius: 8,
    width: '100%',
    alignItems: 'center'
  },
  btnAnalyzeText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 18
  },
  resultBox: { 
    padding: 20, 
    borderRadius: 10, 
    marginTop: 15,
    elevation: 3
  },
  verdictTitle: { 
    fontSize: 22, 
    fontWeight: 'bold', 
    marginBottom: 15, 
    textAlign: 'center' 
  },
  scoreContainer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 15
  },
  scoreLabel: {
    fontSize: 18,
    marginRight: 10
  },
  scoreValue: {
    fontSize: 28,
    fontWeight: 'bold'
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0,0,0,0.1)'
  },
  infoLabel: {
    fontWeight: 'bold',
    color: '#333'
  },
  infoValue: {
    color: '#666',
    fontFamily: 'monospace'
  },
  sectionHeader: { 
    fontWeight: 'bold', 
    marginTop: 15, 
    marginBottom: 8,
    fontSize: 16,
    color: '#333'
  },
  reason: { 
    color: '#c62828', 
    marginTop: 4, 
    fontSize: 14,
    paddingLeft: 5
  },
  tipsCard: {
    backgroundColor: '#e3f2fd',
    padding: 15,
    borderRadius: 10,
    marginTop: 20,
    marginBottom: 30
  },
  tipsTitle: {
    fontWeight: 'bold',
    fontSize: 16,
    marginBottom: 10,
    color: '#1565c0'
  },
  tipItem: {
    color: '#333',
    marginBottom: 5
  }
});
