// Where the "Open the app" / "Explore Intelligence" buttons go.
// Local development uses the Streamlit app on :8501; otherwise set your deployed URL below.
var isLocal = ["localhost", "127.0.0.1", ""].indexOf(location.hostname) !== -1;
window.CONTEXTBRIDGE_CONFIG = {
  appUrl: isLocal ? "http://localhost:8501" : "https://contextbridge-frontend.onrender.com"
};
