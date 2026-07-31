const axios = require('axios');

async function checkComments() {
  const backendUrl = "http://192.168.8.168:8000";
  try {
    // 1. Get layers for case 47
    console.log("Fetching layers for case 47...");
    const layersRes = await axios.get(`${backendUrl}/layers/case/47`);
    const layers = layersRes.data;
    console.log(`Found ${layers.length} layers.`);

    // 2. Fetch features for each layer and check their comments
    for (const layer of layers) {
      console.log(`Fetching features for layer: ${layer.name} (ID: ${layer.id})`);
      const featuresRes = await axios.get(`${backendUrl}/layers/${layer.id}/features`);
      const features = featuresRes.data.features || [];

      for (const feat of features) {
        // Fetch comments directly
        try {
          const commentsRes = await axios.get(`${backendUrl}/features/${feat.id}/comments`);
          const comments = commentsRes.data;
          if (comments && comments.length > 0) {
            console.log(`\nFound comments on Feature "${feat.properties?.name || feat.id}" (Feature ID: ${feat.id}):`);
            console.log(JSON.stringify(comments, null, 2));
          }
        } catch (e) {
          // ignore
        }
      }
    }
  } catch (err) {
    console.error("Error:", err.message);
  }
}

checkComments();
