import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, Button, Image, ActivityIndicator, Alert, TextInput, ScrollView, TouchableOpacity } from 'react-native';
import { Camera } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';

// ⚠️ Mude para o IP do seu computador (use ipconfig/ifconfig)
const API_URL = 'http://10.11.12.172:8000/analyze/vin'; 

export default function App() {
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [image, setImage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  
  // Estado do Formulário
  const [year, setYear] = useState('2020');
  const [model, setModel] = useState('CG 160');
  const [component, setComponent] = useState('chassi'); // 'chassi' ou 'motor'

  useEffect(() => {
    (async () => {
      const { status } = await Camera.requestCameraPermissionsAsync();
      setHasPermission(status === 'granted');
    })();
  }, []);

  const takePicture = async () => {
    let result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 1,
      base64: false,
    });

    if (!result.canceled) {
      setImage(result.assets[0].uri);
      setResult(null);
    }
  };

  const analyzeImage = async () => {
    if (!image) return;

    setLoading(true);
    const formData = new FormData();
    
    // Configuração do arquivo
    formData.append('photo', {
      uri: image,
      name: 'photo.jpg',
      type: 'image/jpeg',
    } as any);

    // Configuração dos campos
    formData.append('year', year);
    formData.append('model', model);
    formData.append('component', component);

    try {
      const response = await axios.post(API_URL, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 10000 // 10 segundos timeout
      });
      setResult(response.data);
    } catch (error) {
      Alert.alert("Erro de Conexão", "Verifique se o backend está rodando e se o IP está correto.");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (hasPermission === null) return <View />;
  if (hasPermission === false) return <Text>Sem acesso à câmera</Text>;

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>PRF Honda Inspector</Text>

      <View style={styles.card}>
        <Text style={styles.label}>Ano Modelo:</Text>
        <TextInput style={styles.input} keyboardType='numeric' value={year} onChangeText={setYear} />
        
        <Text style={styles.label}>Modelo (ex: CG 160):</Text>
        <TextInput style={styles.input} value={model} onChangeText={setModel} />

        <View style={styles.row}>
          <TouchableOpacity 
            style={[styles.btnOption, component === 'chassi' && styles.btnActive]} 
            onPress={() => setComponent('chassi')}>
            <Text style={component === 'chassi' ? styles.textActive : styles.textOption}>CHASSI</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.btnOption, component === 'motor' && styles.btnActive]} 
            onPress={() => setComponent('motor')}>
            <Text style={component === 'motor' ? styles.textActive : styles.textOption}>MOTOR</Text>
          </TouchableOpacity>
        </View>
      </View>

      <Button title="📷 Tirar Foto" onPress={takePicture} />

      {image && (
        <View style={styles.previewContainer}>
          <Image source={{ uri: image }} style={styles.preview} />
          {loading ? (
            <ActivityIndicator size="large" color="#0000ff" />
          ) : (
            <Button title="🔍 ANALISAR AGORA" onPress={analyzeImage} color="red" />
          )}
        </View>
      )}

      {result && (
        <View style={[styles.resultBox, { backgroundColor: result.verdict === 'REGULAR' ? '#d4edda' : '#f8d7da' }]}>
          <Text style={styles.verdictTitle}>{result.verdict}</Text>
          <Text style={styles.text}>Risco: {result.risk_score}%</Text>
          <Text style={styles.text}>Lido: {result.read_code}</Text>
          
          <Text style={styles.sectionHeader}>Motivos:</Text>
          {result.explanation?.length > 0 ? (
            result.explanation.map((item: string, index: number) => (
              <Text key={index} style={styles.reason}>• {item}</Text>
            ))
          ) : (
            <Text style={styles.text}>Nenhuma anomalia detectada.</Text>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, padding: 20, paddingTop: 50, backgroundColor: '#f5f5f5' },
  title: { fontSize: 24, fontWeight: 'bold', marginBottom: 20, textAlign: 'center', color: '#003366' },
  card: { backgroundColor: '#fff', padding: 15, borderRadius: 10, marginBottom: 20, elevation: 3 },
  label: { fontWeight: 'bold', marginBottom: 5 },
  input: { borderWidth: 1, borderColor: '#ddd', padding: 10, marginBottom: 15, borderRadius: 5, backgroundColor: '#fafafa' },
  row: { flexDirection: 'row', justifyContent: 'space-between' },
  btnOption: { flex: 1, padding: 10, alignItems: 'center', borderWidth: 1, borderColor: '#ccc', borderRadius: 5, marginHorizontal: 5 },
  btnActive: { backgroundColor: '#003366', borderColor: '#003366' },
  textOption: { color: '#333' },
  textActive: { color: '#fff', fontWeight: 'bold' },
  previewContainer: { alignItems: 'center', marginVertical: 20 },
  preview: { width: '100%', height: 150, resizeMode: 'contain', marginBottom: 10, borderWidth: 1, borderColor: '#ccc' },
  resultBox: { padding: 20, borderRadius: 8, marginTop: 20 },
  verdictTitle: { fontSize: 20, fontWeight: 'bold', marginBottom: 10, textAlign: 'center' },
  text: { fontSize: 16, marginBottom: 5 },
  sectionHeader: { fontWeight: 'bold', marginTop: 15, marginBottom: 5 },
  reason: { color: '#d9534f', marginTop: 2, fontSize: 14 }
});