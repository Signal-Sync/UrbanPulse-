const API_BASE_URL = "http://127.0.0.1:8000";


export async function predictRoadCondition(imageFile) {
  const formData = new FormData();

  formData.append("file", imageFile);

  const response = await fetch(
    `${API_BASE_URL}/predict`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    const errorData = await response.json();

    throw new Error(
      errorData.detail || "Prediction failed"
    );
  }

  return await response.json();
}


export function getResultImageUrl(imagePath) {
  return `${API_BASE_URL}${imagePath}`;
}


export async function checkBackendHealth() {
  const response = await fetch(
    `${API_BASE_URL}/health`
  );

  return await response.json();
}

const API_BASE_URL = 'http://localhost:8000';

export async function predictImage(imageBlob) {
  const formData = new FormData();

  formData.append(
    'file',
    imageBlob,
    'camera-frame.jpg'
  );

  const response = await fetch(
    `${API_BASE_URL}/predict`,
    {
      method: 'POST',
      body: formData
    }
  );

  if (!response.ok) {
    const error = await response.text();

    throw new Error(
      error || 'Prediction request failed'
    );
  }

  return response.json();
}