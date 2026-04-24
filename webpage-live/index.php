<?php
session_start();

// This is a hastily vibecoded previewer, if everything works. Will not remain in prod.

// --- 1. CONFIGURATION ---
include "db.php";

// SHA-256 hash for the password "admin123"
$hardcoded_hash = '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9';

// --- 2. AUTHENTICATION LOGIC ---
$login_error = false;

// Handle login form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['password'])) {
    if (hash('sha256', $_POST['password']) === $hardcoded_hash) {
        $_SESSION['authenticated'] = true;
        // Redirect to avoid form resubmission on refresh
        header("Location: " . $_SERVER['PHP_SELF']); 
        exit;
    } else {
        $login_error = true;
    }
}

// --- 3. API ENDPOINTS (Returns JSON to the map) ---
// If the user requests data but isn't logged in, block them.
if (isset($_GET['action'])) {
    header('Content-Type: application/json');
    
    if (empty($_SESSION['authenticated'])) {
        http_response_code(401);
        echo json_encode(['error' => 'Unauthorized']);
        exit;
    }

    try {
        $pdo = new PDO("mysql:host=$db_host;dbname=$db_name;charset=utf8mb4", $db_user, $db_pass);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

        if ($_GET['action'] === 'get_tags') {
            $stmt = $pdo->query("SELECT name, hashed_key FROM tags");
            echo json_encode($stmt->fetchAll(PDO::FETCH_ASSOC));
            exit;
        }

        if ($_GET['action'] === 'get_locations' && isset($_GET['key'])) {
            $minConfidence = isset($_GET['confidence']) ? intval($_GET['confidence']) : 1;
            $stmt = $pdo->prepare("SELECT latitude, longitude, time FROM location_data WHERE hashed_key = ? AND confidence >= ? ORDER BY time ASC");
            $stmt->execute([$_GET['key'], $minConfidence]);
            echo json_encode($stmt->fetchAll(PDO::FETCH_ASSOC));
            exit;
        }
    } catch (PDOException $e) {
        http_response_code(500);
        echo json_encode(['error' => $e->getMessage()]);
        exit;
    }
}

// --- 4. HTML FRONTEND (Served only if authenticated) ---
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tag Tracker Viewer</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body, html { margin: 0; padding: 0; height: 100%; font-family: sans-serif; background: #f4f4f4; }
        
        /* Login Screen */
        .login-wrapper {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            height: 100vh; background: #2c3e50; color: white;
        }
        .login-wrapper input { padding: 10px; margin: 10px 0; width: 200px; border-radius: 4px; border: none; }
        .login-wrapper button { padding: 10px 20px; cursor: pointer; background: #3498db; border: none; color: white; border-radius: 4px;}
        
        /* Main App Screen */
        #app-screen { display: flex; height: 100vh; flex-direction: column; }
        #top-bar { padding: 15px; background: #fff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); z-index: 1000; display: flex; align-items: center; gap: 15px; }
        #top-bar select { padding: 8px; font-size: 16px; border-radius: 4px; }
        #map { flex-grow: 1; width: 100%; }
        
        /* Legend */
        .legend { font-size: 14px; display: flex; align-items: center; gap: 10px; margin-left: auto; }
        .gradient-box { width: 100px; height: 15px; background: linear-gradient(to right, rgba(255,0,0,0.1), rgba(255,0,0,1)); border: 1px solid #ccc;}
    </style>
</head>
<body>

<?php if (empty($_SESSION['authenticated'])): ?>
    <div class="login-wrapper">
        <h2>Tracker Dashboard</h2>
        <form method="POST">
            <input type="password" name="password" placeholder="Enter password" required />
            <br>
            <button type="submit">Login</button>
        </form>
        <?php if ($login_error): ?>
            <p style="color: #e74c3c;">Incorrect Password</p>
        <?php endif; ?>
    </div>
<?php else: ?>
    <div id="app-screen">
        <div id="top-bar">
            <label for="tag-select"><strong>Select Tracker:</strong></label>
            <select id="tag-select" onchange="loadMapData()">
                <option value="" disabled selected>Loading tags...</option>
            </select>
            
            <label for="time-scale" style="margin-left: 20px;"><strong>Time Scale:</strong></label>
            <select id="time-scale" onchange="loadMapData()">
                <option value="24h">Last 24 Hours</option>
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
                <option value="all" selected>All Time</option>
            </select>
            
            <label for="confidence" style="margin-left: 20px;"><strong>Min Confidence:</strong></label>
            <select id="confidence" onchange="loadMapData()">
                <option value="1" selected>1</option>
                <option value="2">2</option>
                <option value="3">3</option>
            </select>
            
            <div class="legend" style="margin-left: 30px;">
                <span style="font-size: 12px;">Each day has a different color</span>
            </div>
        </div>
        <div id="map"></div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        let map;
        let mapLayers = []; 

        // Initialize the map once the DOM loads
        document.addEventListener('DOMContentLoaded', () => {
            map = L.map('map').setView([48.1486, 17.1077], 13);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '© OpenStreetMap'
            }).addTo(map);

            fetchTags();
        });

        async function fetchTags() {
            try {
                // Calls the PHP block at the top of the file via the GET action
                const response = await fetch('?action=get_tags');
                const tags = await response.json();
                
                const select = document.getElementById('tag-select');
                select.innerHTML = '<option value="" disabled selected>Select a tracker...</option>';
                
                tags.forEach(tag => {
                    const option = document.createElement('option');
                    option.value = tag.hashed_key;
                    option.textContent = tag.name;
                    select.appendChild(option);
                });
            } catch (err) {
                console.error("Error fetching tags:", err);
            }
        }

        async function loadMapData() {
            const tagKey = document.getElementById('tag-select').value;
            const timeScale = document.getElementById('time-scale').value;
            const confidence = document.getElementById('confidence').value;
            if (!tagKey) return;

            try {
                const response = await fetch(`?action=get_locations&key=${encodeURIComponent(tagKey)}&confidence=${encodeURIComponent(confidence)}`);
                const allLocations = await response.json();
                
                // Filter by time scale
                const filteredLocations = filterByTimeScale(allLocations, timeScale);
                drawLocations(filteredLocations);
            } catch (err) {
                console.error("Error fetching locations:", err);
            }
        }

        function filterByTimeScale(locations, timeScale) {
            const now = new Date();
            let cutoffDate;

            switch (timeScale) {
                case '24h':
                    cutoffDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
                    break;
                case '7d':
                    cutoffDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                    break;
                case '30d':
                    cutoffDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                    break;
                case 'all':
                default:
                    return locations;
            }

            return locations.filter(loc => new Date(loc.time) >= cutoffDate);
        }

        function getDayColor(date, totalDays) {
            // Generate a color palette for different days
            const hue = (date.getDay() * 51.4) % 360; // Spread days across hue range
            const saturation = 70;
            const lightness = 45;
            return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
        }

        function drawLocations(locations) {
            // Clear previous tracks
            mapLayers.forEach(layer => map.removeLayer(layer));
            mapLayers = [];

            if (locations.length === 0) {
                alert("No location data found for this tracker in the selected time period.");
                return;
            }

            const latLngs = [];
            const dayGroups = {}; // Group locations by day

            // Group locations by day
            locations.forEach(loc => {
                const locDate = new Date(loc.time);
                const dayKey = locDate.toISOString().split('T')[0]; // YYYY-MM-DD format
                
                if (!dayGroups[dayKey]) {
                    dayGroups[dayKey] = [];
                }
                dayGroups[dayKey].push(loc);
            });

            // Draw lines and dots for each location, colored by day
            for (let i = 0; i < locations.length; i++) {
                const loc = locations[i];
                const locDate = new Date(loc.time);
                const dayKey = locDate.toISOString().split('T')[0];
                const color = getDayColor(locDate, Object.keys(dayGroups).length);
                
                const currentPoint = [loc.latitude, loc.longitude];
                latLngs.push(currentPoint);

                // Connecting Line
                if (i > 0) {
                    const prevPoint = [locations[i-1].latitude, locations[i-1].longitude];
                    const polyline = L.polyline([prevPoint, currentPoint], {
                        color: color,
                        weight: 4,
                        opacity: 0.8
                    }).addTo(map);
                    mapLayers.push(polyline);
                }

                // Visible GPS Dot
                const circle = L.circleMarker(currentPoint, {
                    radius: 7,
                    fillColor: color,
                    color: '#fff',
                    weight: 1,
                    fillOpacity: 0.9
                }).addTo(map);

                // Invisible larger clickable area
                const invisibleCircle = L.circleMarker(currentPoint, {
                    radius: 30,
                    fillColor: 'transparent',
                    color: 'transparent',
                    weight: 0,
                    fillOpacity: 0
                }).bindPopup(`Date: ${dayKey}<br>Time: ${loc.time}`).addTo(map);
                mapLayers.push(invisibleCircle);
                
                mapLayers.push(circle);
            }

            // Frame the map around the points
            const bounds = L.latLngBounds(latLngs);
            map.fitBounds(bounds, { padding: [50, 50] });
        }
    </script>
<?php endif; ?>
</body>
</html>