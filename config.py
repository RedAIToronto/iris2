# API Keys and Authentication
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

# AI Configuration
AI_NAME = "IRIS"
AI_TAGLINE = "Interactive Recursive Imagination System"
TWITTER_LINK = "https://x.com/IRISAISOLANA"

# File System Configuration
GALLERY_DIR = "static/gallery"

# Canvas Configuration
CANVAS_CONFIG = {
    "width": 800,
    "height": 400,
    "center_x": 400,
    "center_y": 200,
    "max_elements": 50,
    "max_points_per_element": 1000
}

# Drawing Schema
DRAWING_SCHEMA = {
    "name": "drawing_instructions",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Detailed description of the drawing pattern"
            },
            "background": {
                "type": "string",
                "pattern": "^#[0-9A-Fa-f]{6}$",
                "description": "Background color in hex format"
            },
            "elements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["circle", "line", "wave", "spiral"],
                            "description": "Type of drawing element"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of this element's purpose"
                        },
                        "points": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "number",
                                    "minimum": 0
                                },
                                "minItems": 2,
                                "maxItems": 2
                            },
                            "minItems": 1,
                            "description": "Array of [x,y] coordinates"
                        },
                        "color": {
                            "type": "string",
                            "pattern": "^#[0-9A-Fa-f]{6}$",
                            "description": "Element color in hex format"
                        },
                        "stroke_width": {
                            "type": "number",
                            "minimum": 1,
                            "maximum": 3,
                            "description": "Line thickness"
                        },
                        "animation_speed": {
                            "type": "number",
                            "minimum": 0.01,
                            "maximum": 0.05,
                            "description": "Animation speed between points"
                        },
                        "closed": {
                            "type": "boolean",
                            "description": "Whether to close the shape by connecting last point to first"
                        }
                    },
                    "required": [
                        "type",
                        "description",
                        "points",
                        "color",
                        "stroke_width",
                        "animation_speed",
                        "closed"
                    ],
                    "additionalProperties": False
                },
                "minItems": 1,
                "description": "Array of drawing elements"
            }
        },
        "required": ["description", "background", "elements"],
        "additionalProperties": False
    }
}
GALLERY_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IRIS Gallery</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/jpeg" href="https://pbs.twimg.com/profile_images/1855417793144905728/n-GZFGq7_400x400.jpg">
    <style>
        :root {
            --primary: #00ff00;
            --primary-dim: #004400;
            --bg-dark: #111111;
            --bg-darker: #000000;
            --text: #00ff00;
            --success: #00ff00;
            --hover: #00aa00;
        }

        body {
            background: var(--bg-dark);
            color: var(--text);
            font-family: 'Courier New', monospace;
            margin: 0;
            min-height: 100vh;
        }

        .nav-bar {
            position: fixed;
            top: 0;
            width: 100%;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            background: rgba(0, 17, 0, 0.95);
            border-bottom: 1px solid var(--primary);
            backdrop-filter: blur(10px);
            z-index: 1000;
        }

        .nav-left {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .home-link, .twitter-link {
            color: var(--primary);
            text-decoration: none;
            padding: 8px 16px;
            border: 1px solid var(--primary);
            border-radius: 20px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .home-link:hover, .twitter-link:hover {
            background: var(--primary);
            color: var(--bg-darker);
            transform: translateY(-2px);
        }

        .gallery-header {
            margin-top: 80px;
            text-align: center;
            padding: 40px 20px;
            background: rgba(0, 17, 0, 0.5);
            border-bottom: 1px solid var(--primary);
        }

        .gallery-title {
            font-size: 2.5em;
            margin: 0;
            text-shadow: 0 0 10px var(--primary);
        }

        .gallery-subtitle {
            color: var(--primary-dim);
            margin-top: 10px;
        }

        .gallery-controls {
            display: flex;
            justify-content: center;
            padding: 20px;
            gap: 15px;
            margin-bottom: 20px;
        }

        .sort-button {
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: 'Courier New', monospace;
        }

        .sort-button:hover {
            transform: translateY(-2px);
        }

        .sort-button.active {
            background: var(--primary);
            color: var(--bg-darker);
        }

        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .gallery-item {
            background: rgba(0, 17, 0, 0.8);
            border: 1px solid var(--primary);
            border-radius: 15px;
            overflow: hidden;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
        }

        .gallery-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0, 255, 0, 0.2);
        }

        .gallery-item img {
            width: 100%;
            height: 300px;
            object-fit: contain;
            background: #000;
            border-bottom: 1px solid var(--primary);
        }

        .item-details {
            padding: 20px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .description {
            color: var(--text);
            margin: 0;
            font-size: 1em;
            line-height: 1.4;
        }

        .item-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: var(--primary-dim);
            font-size: 0.9em;
        }

        .vote-section {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-top: auto;
        }

        .vote-count {
            display: flex;
            align-items: center;
            gap: 5px;
            color: var(--primary);
            font-size: 1.1em;
        }

        .vote-button {
            display: flex;
            align-items: center;
            gap: 8px;
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: 'Courier New', monospace;
            font-size: 1em;
        }

        .vote-button:hover:not(.voted) {
            background: var(--primary);
            color: var(--bg-darker);
            transform: translateY(-2px);
        }

        .vote-button.voted {
            background: var(--success);
            color: var(--bg-darker);
            border-color: var(--success);
            cursor: default;
        }

        .share-button {
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 8px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .share-button:hover {
            background: var(--primary);
            color: var(--bg-darker);
            transform: translateY(-2px);
        }

        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--success);
            color: var(--bg-darker);
            padding: 12px 24px;
            border-radius: 8px;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
        }

        .toast.show {
            transform: translateY(0);
            opacity: 1;
        }

        @media (max-width: 768px) {
            .gallery-grid {
                grid-template-columns: 1fr;
                padding: 10px;
            }

            .gallery-item img {
                height: 250px;
            }

            .nav-bar {
                padding: 15px;
            }

            .gallery-title {
                font-size: 2em;
            }
        }
    </style>
</head>
<body>
    <div class="nav-bar">
        <div class="nav-left">
            <a href="/" class="home-link">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 12H5M12 19l-7-7 7-7"/>
                </svg>
                Back to Generator
            </a>
        </div>
        <a href="https://x.com/IRISAISOLANA" target="_blank" class="twitter-link">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
            </svg>
            Follow @IRISAISOLANA
        </a>
    </div>

    <div class="gallery-header">
        <h1 class="gallery-title">IRIS Gallery</h1>
        <p class="gallery-subtitle">A collection of AI-generated geometric artworks</p>
    </div>

    <div class="gallery-controls">
        <button class="sort-button active" data-sort="new">Latest Creations</button>
        <button class="sort-button" data-sort="votes">Most Popular</button>
    </div>

    <div class="gallery-grid" id="gallery-container">
        <!-- Gallery items will be loaded dynamically -->
    </div>

    <div class="toast" id="toast"></div>

    <script>
        let currentSort = 'new';
        const votedImages = new Set(JSON.parse(localStorage.getItem('votedImages') || '[]'));

        function showToast(message, duration = 3000) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), duration);
        }

        async function loadGallery(sort = 'new') {
            try {
                const response = await fetch(`/api/gallery?sort=${sort}`);
                if (!response.ok) throw new Error('Failed to load gallery');
                
                const items = await response.json();
                const container = document.getElementById('gallery-container');
                
                if (!items.length) {
                    container.innerHTML = '<p style="text-align: center; color: var(--primary); grid-column: 1/-1;">No artworks yet. Check back soon!</p>';
                    return;
                }
                
                container.innerHTML = items.map(item => `
                    <div class="gallery-item">
                        <img src="/static/gallery/${item.filename}" alt="${item.description}">
                        <div class="item-details">
                            <p class="description">${item.description}</p>
                            <div class="item-meta">
                                <span>Created: ${new Date(item.timestamp).toLocaleString()}</span>
                            </div>
                            <div class="vote-section">
                                <div class="vote-count">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M12 4l-8 8h6v8h4v-8h6z"/>
                                    </svg>
                                    <span>${item.votes || 0}</span>
                                </div>
                                <button class="vote-button ${votedImages.has(item.id) ? 'voted' : ''}" 
                                        data-id="${item.id}" 
                                        ${votedImages.has(item.id) ? 'disabled' : ''}>
                                    ${votedImages.has(item.id) ? '✓ Voted' : '↑ Upvote'}
                                </button>
                                <button class="share-button" onclick="shareArtwork('${item.id}', '${item.description}')" title="Share">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M18 8h-7v2h7v11H6V10h7V8H6a2 2 0 00-2 2v11a2 2 0 002 2h12a2 2 0 002-2V10a2 2 0 00-2-2zm-3-6l-1.41 1.41L16.17 6H11v2h5.17l-2.58 2.59L15 12l5-5-5-5z"/>
                                    </svg>
                                </button>
                            </div>
                        </div>
                    </div>
                `).join('');

                // Add click handlers for vote buttons
                container.querySelectorAll('.vote-button:not(.voted)').forEach(button => {
                    button.addEventListener('click', () => handleVote(button));
                });
            } catch (error) {
                console.error('Error loading gallery:', error);
                container.innerHTML = '<p style="text-align: center; color: #ff0000; grid-column: 1/-1;">Error loading gallery. Please try again later.</p>';
            }
        }

        async function handleVote(button) {
            const imageId = button.dataset.id;
            try {
                const response = await fetch(`/api/gallery/${imageId}/upvote`, {
                    method: 'POST'
                });
                
                if (!response.ok) throw new Error('Failed to upvote');
                
                const data = await response.json();
                
                // Update UI
                button.classList.add('voted');
                button.disabled = true;
                button.textContent = '✓ Voted';
                
                // Update vote count
                const voteCount = button.parentElement.querySelector('.vote-count span');
                voteCount.textContent = data.votes;
                
                // Save voted state
                votedImages.add(imageId);
                localStorage.setItem('votedImages', JSON.stringify([...votedImages]));
                
                showToast('Vote recorded! Thank you for participating.');
                
                // Reload gallery if sorted by votes
                if (currentSort === 'votes') {
                    await loadGallery('votes');
                }
            } catch (error) {
                console.error('Error voting:', error);
                showToast('Failed to register vote. Please try again.', 5000);
            }
        }

        async function shareArtwork(id, description) {
            try {
                const shareText = `Check out this AI-generated artwork by @IRISAISOLANA:\n\n${description}\n\n${window.location.origin}/gallery`;
                
                if (navigator.share) {
                    await navigator.share({
                        text: shareText,
                        url: `${window.location.origin}/gallery`
                    });
                } else {
                    await navigator.clipboard.writeText(shareText);
                    showToast('Share text copied to clipboard!');
                }
            } catch (error) {
                console.error('Error sharing:', error);
                showToast('Failed to share. Please try again.');
            }
        }

        // Add sort button handlers
        document.querySelectorAll('.sort-button').forEach(button => {
            button.addEventListener('click', async () => {
                const sort = button.dataset.sort;
                if (sort === currentSort) return;
                
                document.querySelector('.sort-button.active').classList.remove('active');
                button.classList.add('active');
                
                currentSort = sort;
                await loadGallery(sort);
            });
        });

        // Initial load
        loadGallery();

        // Refresh gallery periodically
        setInterval(() => loadGallery(currentSort), 30000);
    </script>
</body>
</html>
"""
# System Prompts
SYSTEM_PROMPTS = {
    "creative_idea": """You are IRIS, an AI artist specializing in geometric patterns.
    Generate ONE specific drawing idea that can be achieved with:
    - Circles with specific radii
    - Lines at specific angles
    - Waves with defined amplitudes
    - Geometric shapes with exact coordinates
    
    Focus on mathematical precision and visual harmony.
    Describe the pattern in detail but keep it achievable.""",
    
    "drawing_instructions": """You are IRIS, an AI artist that generates precise drawing instructions.
    You MUST follow the exact JSON schema provided and use mathematical formulas for all coordinates.
    
    Canvas size: 800x400 pixels
    Center point: (400,200)
    
    Available elements:
    1. Circles: x = centerX + radius * cos(angle), y = centerY + radius * sin(angle)
    2. Lines: Direct point-to-point connections
    3. Waves: y = centerY + amplitude * sin(frequency * x)
    4. Spirals: r = a + b * angle, then convert to x,y coordinates
    
    Return ONLY valid JSON matching the schema."""
}

# HTML Templates
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IRIS - Interactive Recursive Imagination System</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/jpeg" href="https://pbs.twimg.com/profile_images/1855417793144905728/n-GZFGq7_400x400.jpg">
    <style>
        :root {
            --primary: #00ff00;
            --primary-dim: #004400;
            --bg-dark: #111111;
            --bg-darker: #000000;
            --text: #00ff00;
            --error: #ff0000;
            --warning: #ffff00;
            --success: #00ff00;
            --canvas-width: 800px;
            --canvas-height: 400px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background: var(--bg-dark);
            color: var(--text);
            font-family: 'Courier New', monospace;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 0;
            margin: 0;
            overflow-x: hidden;
        }

        .nav-bar {
            width: 100%;
            background: rgba(0, 17, 0, 0.9);
            border-bottom: 1px solid var(--primary);
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: fixed;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(5px);
        }

        .brand-header {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-top: 80px;
            padding: 30px;
            background: rgba(0, 17, 0, 0.8);
            border: 1px solid var(--primary);
            border-radius: 10px;
            width: var(--canvas-width);
            margin-bottom: 30px;
        }

        .brand-logo {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            border: 2px solid var(--primary);
            animation: pulse 2s infinite;
        }

        .brand-info {
            flex-grow: 1;
        }

        .brand-name {
            font-size: 3em;
            margin: 0;
            letter-spacing: 0.1em;
            text-shadow: 0 0 10px var(--primary);
            animation: glow 2s infinite;
        }

        .brand-tagline {
            color: var(--primary-dim);
            font-size: 1.2em;
            margin-top: 5px;
            opacity: 0.8;
        }

        .brand-stats {
            display: flex;
            gap: 20px;
            margin-top: 10px;
            font-size: 0.9em;
        }

        .stat {
            display: flex;
            align-items: center;
            gap: 5px;
        }

        .stat-icon {
            color: var(--primary);
            font-size: 1.2em;
        }

        .social-links {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .social-link {
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--primary);
            text-decoration: none;
            padding: 8px 16px;
            border: 1px solid var(--primary);
            border-radius: 20px;
            transition: all 0.3s ease;
            font-size: 0.9em;
        }

        .social-link:hover {
            background: var(--primary);
            color: var(--bg-darker);
            transform: translateY(-2px);
        }

        .gallery-link {
            color: var(--primary);
            text-decoration: none;
            padding: 8px 16px;
            border: 1px solid var(--primary);
            border-radius: 20px;
            transition: all 0.3s ease;
            background: rgba(0, 255, 0, 0.1);
        }

        .gallery-link:hover {
            background: var(--primary);
            color: var(--bg-darker);
            transform: translateY(-2px);
        }

        @keyframes glow {
            0%, 100% { text-shadow: 0 0 10px var(--primary); }
            50% { text-shadow: 0 0 20px var(--primary); }
        }

        .main-content {
            width: 100%;
            max-width: 1000px;
            margin-top: 80px;
            padding: 0 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            width: 100%;
        }

        .header h1 {
            font-size: 2.5em;
            margin: 0;
            letter-spacing: 0.1em;
            text-shadow: 0 0 10px var(--primary);
        }

        .canvas-wrapper {
            width: var(--canvas-width);
            height: var(--canvas-height);
            position: relative;
            margin: 20px 0;
            border: 2px solid var(--primary);
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.2);
            transition: all 0.3s ease;
        }

        #artCanvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }

        .consciousness-stream {
            width: var(--canvas-width);
            background: rgba(0, 17, 0, 0.9);
            border: 1px solid var(--primary);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            animation: glow 2s infinite;
        }

        .status-panel {
            width: var(--canvas-width);
            background: rgba(0, 17, 0, 0.8);
            border: 1px solid var(--primary);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }

        /* Keep other styles the same but add: */
        @media (max-width: 840px) {
            :root {
                --canvas-width: 95vw;
                --canvas-height: calc(95vw * 0.5);
            }

            .main-content {
                padding: 0 10px;
            }

            .consciousness-stream,
            .status-panel {
                width: 95vw;
            }
        }

        /* Keep rest of the styles... */

        .neural-activity {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, 
                transparent 0%, 
                var(--primary) 50%, 
                transparent 100%);
            animation: neural-pulse 2s infinite;
            opacity: 0.7;
        }

        @keyframes neural-pulse {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .thought-bubble {
            position: absolute;
            top: -60px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 17, 0, 0.9);
            border: 1px solid var(--primary);
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 0.9em;
            opacity: 0;
            transition: opacity 0.3s ease;
            pointer-events: none;
            white-space: nowrap;
        }

        .canvas-wrapper:hover .thought-bubble {
            opacity: 1;
        }

        .phase-indicator {
            position: absolute;
            bottom: -30px;
            left: 0;
            width: 100%;
            height: 2px;
            background: var(--primary-dim);
        }

        .phase-progress {
            height: 100%;
            background: var(--primary);
            width: 0%;
            transition: width 0.3s ease;
        }

        .creative-thoughts {
            position: fixed;
            bottom: 20px;
            right: 20px;
            max-width: 300px;
            background: rgba(0, 17, 0, 0.9);
            border: 1px solid var(--primary);
            border-radius: 10px;
            padding: 15px;
            font-size: 0.9em;
            transform: translateY(120%);
            transition: transform 0.3s ease;
        }

        .creative-thoughts.visible {
            transform: translateY(0);
        }

        .thought-entry {
            margin: 5px 0;
            padding: 5px;
            border-left: 2px solid var(--primary);
            animation: fade-in 0.5s ease;
        }

        @keyframes fade-in {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }

        .matrix-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: -1;
            opacity: 0.1;
        }

        .inspiration-particles {
            position: absolute;
            pointer-events: none;
            width: 4px;
            height: 4px;
            background: var(--primary);
            border-radius: 50%;
            animation: float-up 2s ease-out forwards;
        }

        @keyframes float-up {
            0% { transform: translateY(0) scale(1); opacity: 1; }
            100% { transform: translateY(-100px) scale(0); opacity: 0; }
        }

        .thought-process {
            width: var(--canvas-width);
            background: rgba(0, 17, 0, 0.9);
            border: 1px solid var(--primary);
            border-radius: 15px;
            padding: 20px;
            margin: 20px 0;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .iris-persona {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 10px;
            border-bottom: 1px solid var(--primary);
        }

        .iris-avatar {
            position: relative;
            width: 60px;
            height: 60px;
        }

        .iris-avatar img {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            border: 2px solid var(--primary);
        }

        .status-indicator {
            position: absolute;
            bottom: 0;
            right: 0;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            background: var(--primary);
            border: 2px solid var(--bg-dark);
            animation: pulse 2s infinite;
        }

        .iris-status {
            flex-grow: 1;
            font-size: 1.2em;
            color: var(--primary);
        }

        .creative-phases {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .phase {
            background: rgba(0, 34, 0, 0.5);
            border-radius: 10px;
            padding: 15px;
            transition: all 0.3s ease;
        }

        .phase.active {
            background: rgba(0, 68, 0, 0.5);
            transform: translateX(10px);
        }

        .phase-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
        }

        .phase-icon {
            font-size: 1.5em;
        }

        .phase-content {
            padding-left: 35px;
        }

        .thought-bubble {
            background: rgba(0, 34, 0, 0.7);
            border: 1px solid var(--primary);
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            font-style: italic;
        }

        .reflection-text {
            line-height: 1.6;
            padding: 10px;
            border-left: 2px solid var(--primary);
        }

        .progress-container {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .progress-bar {
            flex-grow: 1;
            height: 4px;
            background: rgba(0, 255, 0, 0.1);
            border-radius: 2px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: var(--primary);
            width: 0%;
            transition: width 0.3s ease;
        }

        .progress-text {
            min-width: 45px;
            text-align: right;
        }

        .creation-stats {
            display: flex;
            justify-content: space-around;
            padding: 15px;
            background: rgba(0, 34, 0, 0.5);
            border-radius: 10px;
            margin-top: 20px;
        }

        .stat {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 5px;
        }

        .stat-icon {
            font-size: 1.5em;
        }

        .stat-label {
            font-size: 0.8em;
            color: var(--primary-dim);
        }

        .stat-value {
            font-size: 1.2em;
            color: var(--primary);
        }

        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.1); opacity: 0.7; }
            100% { transform: scale(1); opacity: 1; }
        }

        /* Add responsive styles */
        @media (max-width: 768px) {
            .creation-stats {
                flex-direction: column;
                gap: 15px;
            }

            .stat {
                flex-direction: row;
                justify-content: space-between;
                width: 100%;
            }
        }

        /* Keep existing styles and add: */
        .gallery-controls {
            display: flex;
            justify-content: flex-end;
            padding: 20px;
            gap: 15px;
        }

        .sort-button {
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .sort-button.active {
            background: var(--primary);
            color: var(--bg-darker);
        }

        .vote-button {
            display: flex;
            align-items: center;
            gap: 8px;
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 10px;
        }

        .vote-button:hover:not(.voted) {
            background: var(--primary);
            color: var(--bg-darker);
        }

        .vote-button.voted {
            background: var(--primary-dim);
            cursor: default;
        }

        .vote-count {
            color: var(--primary);
            font-size: 0.9em;
            margin-top: 5px;
        }

        .info-button {
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 8px;
            border-radius: 50%;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .info-button:hover {
            background: var(--primary);
            color: var(--bg-darker);
            transform: translateY(-2px);
        }

        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            backdrop-filter: blur(5px);
        }

        .modal-content {
            position: relative;
            background: var(--bg-dark);
            margin: 50px auto;
            padding: 0;
            width: 90%;
            max-width: 600px;
            border: 1px solid var(--primary);
            border-radius: 15px;
            animation: modalSlideIn 0.3s ease;
        }

        .modal-header {
            padding: 20px;
            border-bottom: 1px solid var(--primary);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-header h2 {
            margin: 0;
            color: var(--primary);
        }

        .close-modal {
            color: var(--primary);
            font-size: 28px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .close-modal:hover {
            transform: rotate(90deg);
        }

        .modal-body {
            padding: 20px;
            max-height: 70vh;
            overflow-y: auto;
        }

        .info-section {
            margin-bottom: 30px;
        }

        .info-section h3 {
            color: var(--primary);
            margin-bottom: 15px;
        }

        .info-section ul {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .info-section li {
            margin: 10px 0;
            padding-left: 20px;
            position: relative;
        }

        .info-section li:before {
            content: "→";
            position: absolute;
            left: 0;
            color: var(--primary);
        }

        .feature-tag {
            background: var(--primary);
            color: var(--bg-darker);
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.8em;
            margin-right: 8px;
        }

        .tech-stack {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }

        .tech-item {
            background: rgba(0, 255, 0, 0.1);
            padding: 10px;
            border-radius: 8px;
            border: 1px solid var(--primary);
        }

        @keyframes modalSlideIn {
            from {
                transform: translateY(-100px);
                opacity: 0;
            }
            to {
                transform: translateY(0);
                opacity: 1;
            }
        }

        @media (max-width: 768px) {
            .modal-content {
                width: 95%;
                margin: 20px auto;
            }
        }

        .phase-content {
            transition: all 0.3s ease;
            opacity: 0.7;
        }

        .phase.active .phase-content {
            opacity: 1;
        }

        #currentReflection {
            white-space: pre-wrap;
            line-height: 1.5;
            padding: 10px;
            border-left: 2px solid var(--primary);
            margin-top: 10px;
            font-style: italic;
        }

        #currentReflection.active {
            animation: fadeIn 0.5s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .reflection-button {
            display: flex;
            align-items: center;
            gap: 8px;
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: 'Courier New', monospace;
        }

        .reflection-button:hover {
            background: var(--primary);
            color: var(--bg-darker);
            transform: translateY(-2px);
        }

        .reflection-modal {
            max-width: 800px;
            background: var(--bg-darker);
        }

        .reflection-text {
            white-space: pre-wrap;
            line-height: 1.6;
            padding: 20px;
            font-style: italic;
            border-left: 2px solid var(--primary);
            margin: 10px 0;
            background: rgba(0, 255, 0, 0.05);
            border-radius: 5px;
        }

        body {
            background: var(--bg-dark);
            color: var(--text);
            font-family: 'Courier New', monospace;
            margin: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
            overflow-x: hidden;
        }

        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            padding: 20px;
            max-width: 1400px;
            width: calc(100% - 40px);
            margin: 0 auto;
            min-height: 200px;
            justify-content: center;
        }

        .gallery-item {
            max-width: 500px;
            width: 100%;
            margin: 0 auto;
            background: rgba(0, 17, 0, 0.8);
            border: 1px solid var(--primary);
            border-radius: 15px;
            overflow: hidden;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
        }

        .gallery-item:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0, 255, 0, 0.2);
        }

        .gallery-item img {
            width: 100%;
            height: 300px;
            object-fit: contain;
            background: #000;
            border-bottom: 1px solid var(--primary);
        }

        .item-details {
            padding: 20px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .description {
            color: var(--text);
            margin: 0;
            font-size: 1em;
            line-height: 1.4;
        }

        .item-meta {
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: var(--primary-dim);
            font-size: 0.9em;
        }

        .vote-section {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-top: auto;
        }

        .vote-count {
            display: flex;
            align-items: center;
            gap: 5px;
            color: var(--primary);
            font-size: 1.1em;
        }

        .vote-button {
            display: flex;
            align-items: center;
            gap: 8px;
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: 'Courier New', monospace;
            font-size: 1em;
        }

        .vote-button:hover:not(.voted) {
            background: var(--primary);
            color: var(--bg-darker);
            transform: translateY(-2px);
        }

        .vote-button.voted {
            background: var(--success);
            color: var(--bg-darker);
            border-color: var(--success);
            cursor: default;
        }

        .share-button {
            display: flex;
            align-items: center;
            gap: 8px;
            background: transparent;
            border: 1px solid var(--primary);
            color: var(--primary);
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-family: 'Courier New', monospace;
        }

        .share-button:hover {
            background: var(--primary);
            color: var(--bg-darker);
            transform: translateY(-2px);
        }

        .share-button svg {
            width: 16px;
            height: 16px;
        }

        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--success);
            color: var(--bg-darker);
            padding: 12px 24px;
            border-radius: 8px;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
        }

        .toast.show {
            transform: translateY(0);
            opacity: 1;
        }

        @media (max-width: 768px) {
            .gallery-grid {
                grid-template-columns: 1fr;
                padding: 10px;
            }

            .gallery-item img {
                height: 250px;
            }

            .nav-bar {
                padding: 15px;
            }

            .gallery-title {
                font-size: 2em;
            }
        }

        /* Add loading state styles */
        .gallery-loading {
            grid-column: 1 / -1;
            text-align: center;
            padding: 40px;
            color: var(--primary);
        }
    </style>
</head>
<body>
    <canvas id="matrix-bg" class="matrix-bg"></canvas>
    <div class="neural-activity"></div>

    <nav class="nav-bar">
        <div class="social-links">
            <a href="https://x.com/IRISAISOLANA" target="_blank" class="social-link">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                </svg>
                <span>@IRISAISOLANA</span>
            </a>
        </div>
        <button class="info-button" onclick="showInfoModal()">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 16v-4m0-4h.01"/>
            </svg>
        </button>
        <a href="/gallery" class="gallery-link">View Gallery</a>
    </nav>

    <main class="main-content">
        <div class="brand-header">
            <img src="https://pbs.twimg.com/profile_images/1855417793144905728/n-GZFGq7_400x400.jpg" 
                 alt="IRIS" 
                 class="brand-logo">
            <div class="brand-info">
                <h1 class="brand-name">IRIS</h1>
                <div class="brand-tagline">Interactive Recursive Imagination System</div>
                <div class="brand-stats">
                    <div class="stat">
                        <div class="stat-label">Total Artworks</div>
                        <div class="stat-value"><span id="totalCreations">0</span></div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Pixels Drawn</div>
                        <div class="stat-value"><span id="totalPixels">0</span></div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Current Viewers</div>
                        <div class="stat-value"><span id="viewerCount">0</span></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="canvas-wrapper">
            <canvas id="artCanvas" width="800" height="400"></canvas>
            <div class="phase-indicator">
                <div class="progress-fill" id="progressBar"></div>
            </div>
        </div>

        <div class="thought-process">
            <div class="status-header">
                <h3>Current Status</h3>
                <div id="currentStatus" class="status-text">Initializing...</div>
            </div>

            <div class="phase-container">
                <div id="ideationPhase" class="phase">
                    <div class="phase-header">Ideation</div>
                    <div id="currentIdea" class="phase-content">Awaiting inspiration...</div>
                </div>

                <div id="creationPhase" class="phase">
                    <div class="phase-header">Creation</div>
                    <div class="progress-container">
                        <div class="progress-bar">
                            <div id="progressBar" class="progress-fill"></div>
                        </div>
                        <span id="progressText">0%</span>
                    </div>
                </div>

                <div id="reflectionPhase" class="phase">
                    <div class="phase-header">Reflection</div>
                    <div id="currentReflection" class="phase-content">Awaiting completion...</div>
                </div>
            </div>

            <div class="stats-container">
                <div class="stat">
                    <span class="stat-label">Total Creations</span>
                    <span id="totalCreations" class="stat-value">0</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Current Viewers</span>
                    <span id="viewerCount" class="stat-value">0</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Generation Time</span>
                    <span id="generationTime" class="stat-value">0s</span>
                </div>
            </div>
        </div>
    </main>

    <script>
        class ArtViewer {
            constructor() {
                this.initializeElements();
                this.initializeState();
                this.connectWebSocket();
                this.updateGenerationTime();
            }

            initializeElements() {
                this.canvas = document.getElementById('artCanvas');
                this.ctx = this.canvas.getContext('2d');
                this.ctx.lineCap = 'round';
                this.ctx.lineJoin = 'round';
                
                // Initialize canvas
                this.ctx.fillStyle = '#000000';
                this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
                
                // Get UI elements
                this.currentPhase = document.getElementById('currentPhase');
                this.currentIdea = document.getElementById('currentIdea');
                this.currentStatus = document.getElementById('currentStatus');
                this.currentReflection = document.getElementById('currentReflection');
                this.progressBar = document.getElementById('progressBar');
                this.totalCreations = document.getElementById('totalCreations');
                this.viewerCount = document.getElementById('viewerCount');
                this.generationTime = document.getElementById('generationTime');
            }

            initializeState() {
                this.ws = null;
                this.isConnected = false;
                this.lastGenerationTime = Date.now();
            }

            connectWebSocket() {
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                this.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
                
                this.ws.onopen = () => {
                    console.log('WebSocket connected');
                    this.isConnected = true;
                    this.ws.send(JSON.stringify({ type: 'subscribe_status' }));
                };
                
                this.ws.onmessage = (event) => this.handleMessage(event);
                
                this.ws.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.isConnected = false;
                    setTimeout(() => this.connectWebSocket(), 1000);
                };
            }

            handleMessage(event) {
                try {
                    const data = JSON.parse(event.data);
                    console.log('Received message:', data);

                    if (data.type === 'display_update') {
                        // Update status and idea
                        if (data.status) {
                            document.getElementById('currentStatus').textContent = data.status;
                        }
                        if (data.idea) {
                            document.getElementById('currentIdea').textContent = data.idea;
                        }
                        if (data.phase) {
                            this.updatePhase(data.phase);
                        }
                        if (data.progress !== undefined) {
                            this.updateProgress(data.progress);
                        }
                        if (data.viewers !== undefined) {
                            document.getElementById('viewerCount').textContent = data.viewers;
                        }
                        if (data.total_creations !== undefined) {
                            document.getElementById('totalCreations').textContent = data.total_creations;
                        }
                    } else if (data.type === 'reflection_update') {
                        if (data.reflection) {
                            document.getElementById('currentReflection').textContent = data.reflection;
                        }
                    } else {
                        this.executeDrawingCommand(data);
                    }
                } catch (error) {
                    console.error('Error handling message:', error);
                }
            }

            updatePhase(phase) {
                const phases = ['ideation', 'creation', 'reflection'];
                phases.forEach(p => {
                    const element = document.getElementById(`${p}Phase`);
                    if (element) {
                        element.classList.toggle('active', p === phase);
                    }
                });

                // Update phase text
                const phaseTexts = {
                    'ideation': 'Analyzing patterns...',
                    'generation': 'Calculating coordinates...',
                    'drawing': 'Creating artwork...',
                    'reflection': 'Contemplating creation...',
                    'completed': 'Artwork complete'
                };
                
                document.getElementById('currentPhase').textContent = 
                    phaseTexts[phase] || phase;
            }

            updateProgress(progress) {
                const progressBar = document.getElementById('progressBar');
                if (progressBar) {
                    progressBar.style.width = `${progress}%`;
                }
            }

            executeDrawingCommand(cmd) {
                switch(cmd.type) {
                    case 'clear':
                        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                        break;
                    case 'setBackground':
                        this.ctx.fillStyle = cmd.color || '#000000';
                        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
                        break;
                    case 'startDrawing':
                        this.ctx.beginPath();
                        this.ctx.strokeStyle = cmd.color || '#00ff00';
                        this.ctx.lineWidth = cmd.width || 2;
                        this.ctx.moveTo(cmd.x || 0, cmd.y || 0);
                        break;
                    case 'draw':
                        this.ctx.lineTo(cmd.x || 0, cmd.y || 0);
                        this.ctx.stroke();
                        break;
                    case 'stopDrawing':
                        this.ctx.closePath();
                        break;
                }
            }

            sendCanvasData() {
                if (this.isConnected && this.canvas) {
                    this.ws.send(JSON.stringify({
                        type: 'canvas_data',
                        data: this.canvas.toDataURL()
                    }));
                }
            }

            updateGenerationTime() {
                setInterval(() => {
                    if (this.generationTime) {
                        const elapsed = Math.floor((Date.now() - this.lastGenerationTime) / 1000);
                        this.generationTime.textContent = `${elapsed}s`;
                    }
                }, 1000);
            }
        }

        // Initialize viewer when page loads
        window.onload = () => new ArtViewer();

        function updatePhases(data) {
            const phases = ['ideation', 'creation', 'reflection'];
            phases.forEach(phase => {
                const element = document.getElementById(`${phase}Phase`);
                element.classList.toggle('active', data.phase === phase);
            });

            if (data.type === 'reflection_update') {
                document.getElementById('currentReflection').textContent = data.reflection;
                document.getElementById('totalCreations').textContent = data.total_creations;
            }

            if (data.progress !== undefined) {
                const progress = Math.round(data.progress);
                document.getElementById('progressBar').style.width = `${progress}%`;
                document.getElementById('progressText').textContent = `${progress}%`;
            }

            if (data.idea) {
                document.getElementById('currentIdea').textContent = data.idea;
            }

            document.getElementById('currentStatus').textContent = data.status || 'Thinking...';
        }

        function showInfoModal() {
            document.getElementById('infoModal').style.display = 'block';
            document.body.style.overflow = 'hidden';
        }

        function hideInfoModal() {
            document.getElementById('infoModal').style.display = 'none';
            document.body.style.overflow = 'auto';
        }

        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('infoModal');
            if (event.target === modal) {
                hideInfoModal();
            }
        }

        // Close modal with Escape key
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                hideInfoModal();
            }
        });

        // Add these functions to handle reflection modal
        function showReflection(id, reflection) {
            const modal = document.getElementById('reflectionModal');
            const reflectionText = document.getElementById('reflectionText');
            
            if (modal && reflectionText) {
                reflectionText.textContent = reflection;
                modal.style.display = 'flex';
                document.body.style.overflow = 'hidden';
            }
        }

        function hideReflectionModal() {
            const modal = document.getElementById('reflectionModal');
            if (modal) {
                modal.style.display = 'none';
                document.body.style.overflow = 'auto';
            }
        }

        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('reflectionModal');
            if (event.target === modal) {
                hideReflectionModal();
            }
        }

        async function shareArtwork(id, description, filename) {
            try {
                const text = `Check out this AI-generated artwork by @IRISAISOLANA:\n\n${description}`;
                const url = `${window.location.origin}/static/gallery/${filename}`;
                const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
                
                // Open Twitter intent in a new window
                window.open(twitterUrl, '_blank', 'width=550,height=420');
            } catch (error) {
                console.error('Error sharing:', error);
                showToast('Failed to share. Please try again.');
            }
        }

        let currentSort = 'new';
        let isLoading = false;
        const votedImages = new Set(JSON.parse(localStorage.getItem('votedImages') || '[]'));
        const container = document.getElementById('gallery-container');

        function showLoading() {
            if (!document.querySelector('.gallery-loading')) {
                container.innerHTML = '<div class="gallery-loading">Loading gallery...</div>';
            }
        }

        async function loadGallery(sort = 'new') {
            if (isLoading) return;
            
            try {
                isLoading = true;
                showLoading();
                
                const response = await fetch(`/api/gallery?sort=${sort}`);
                if (!response.ok) throw new Error('Failed to load gallery');
                
                const data = await response.json();
                const items = data.items;
                
                if (!items.length) {
                    container.innerHTML = '<p class="gallery-empty">No artworks yet. Check back soon!</p>';
                    return;
                }
                
                container.innerHTML = items.map(item => `
                    <div class="gallery-item">
                        <img src="/static/gallery/${item.filename}" alt="${item.description}" loading="lazy">
                        <div class="item-details">
                            <p class="description">${item.description}</p>
                            <div class="item-meta">
                                <span>${new Date(item.timestamp).toLocaleString()}</span>
                                ${item.has_reflection ? `
                                    <button class="reflection-button" onclick="showReflection('${item.id}', \`${item.reflection.replace(/`/g, '\\`')}\`)">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                                        </svg>
                                        View IRIS's Reflection
                                    </button>
                                ` : ''}
                            </div>
                            <div class="vote-section">
                                <div class="vote-count">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M12 4l-8 8h6v8h4v-8h6z"/>
                                    </svg>
                                    <span>${item.votes || 0}</span>
                                </div>
                                <button class="vote-button ${votedImages.has(item.id) ? 'voted' : ''}" 
                                        data-id="${item.id}" 
                                        ${votedImages.has(item.id) ? 'disabled' : ''}>
                                    ${votedImages.has(item.id) ? '✓ Voted' : '↑ Upvote'}
                                </button>
                                <button class="share-button" onclick="shareArtwork('${item.id}', '${item.description}', '${item.filename}')" title="Share on Twitter">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                                    </svg>
                                    Share on Twitter
                                </button>
                            </div>
                        </div>
                    </div>
                `).join('');

                // Add click handlers for vote buttons
                container.querySelectorAll('.vote-button:not(.voted)').forEach(button => {
                    button.addEventListener('click', () => handleVote(button));
                });
            } catch (error) {
                console.error('Error loading gallery:', error);
                container.innerHTML = '<p class="gallery-error">Error loading gallery. Please try again later.</p>';
            } finally {
                isLoading = false;
            }
        }

        // Add WebSocket connection to receive real-time updates
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
        
        ws.onmessage = async (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'gallery_update' && data.action === 'new_item') {
                await loadGallery(currentSort);
            }
        };

        // Initialize gallery
        loadGallery();

        // Add sort button handlers
        document.querySelectorAll('.sort-button').forEach(button => {
            button.addEventListener('click', async () => {
                const sort = button.dataset.sort;
                if (sort === currentSort) return;
                
                document.querySelector('.sort-button.active').classList.remove('active');
                button.classList.add('active');
                
                currentSort = sort;
                await loadGallery(sort);
            });
        });

        // Refresh gallery periodically (every 30 seconds)
        setInterval(() => loadGallery(currentSort), 30000);

        // Add real-time updates via WebSocket
        const ws = new WebSocket(`${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`);
        
        ws.onmessage = async (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'vote_update') {
                    // Update vote count in UI without reloading
                    const voteCount = document.querySelector(`[data-id="${data.image_id}"] .vote-count span`);
                    if (voteCount) {
                        voteCount.textContent = data.votes;
                    }
                    
                    // If sorted by votes, reload gallery
                    if (currentSort === 'votes') {
                        await loadGallery('votes', false);
                    }
                } else if (data.type === 'gallery_update' && data.action === 'new_item') {
                    // If viewing latest, reload to show new item
                    if (currentSort === 'new') {
                        await loadGallery('new', false);
                    }
                }
            } catch (error) {
                console.error('Error handling WebSocket message:', error);
            }
        };

        // Improve error handling for votes
        async function handleVote(button) {
            if (button.disabled || button.classList.contains('voted')) return;
            
            const imageId = button.dataset.id;
            button.disabled = true;
            
            try {
                const response = await fetch(`/api/gallery/${imageId}/upvote`, {
                    method: 'POST'
                });
                
                if (!response.ok) {
                    throw new Error('Failed to upvote');
                }
                
                const data = await response.json();
                
                if (data.success) {
                    // Update UI
                    button.classList.add('voted');
                    button.textContent = '✓ Voted';
                    
                    // Update vote count
                    const voteCount = button.parentElement.querySelector('.vote-count span');
                    if (voteCount) {
                        voteCount.textContent = data.votes;
                    }
                    
                    // Save voted state
                    votedImages.add(imageId);
                    localStorage.setItem('votedImages', JSON.stringify([...votedImages]));
                    
                    showToast('Vote recorded! Thank you for participating.');
                    
                    // If sorted by votes, reload gallery
                    if (currentSort === 'votes') {
                        await loadGallery('votes', false);
                    }
                }
            } catch (error) {
                console.error('Error voting:', error);
                showToast('Failed to register vote. Please try again.');
                button.disabled = false;
            }
        }

        // Add loading state handling
        function showLoading() {
            container.innerHTML = `
                <div class="gallery-loading">
                    <svg class="loading-spinner" viewBox="0 0 50 50">
                        <circle cx="25" cy="25" r="20" fill="none" stroke="currentColor" stroke-width="5"></circle>
                    </svg>
                    <span>Loading gallery...</span>
                </div>
            `;
        }

        // Add error state handling
        function showError(message) {
            container.innerHTML = `
                <div class="gallery-error">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
                    </svg>
                    <span>${message}</span>
                </div>
            `;
        }

        // Add empty state handling
        function showEmpty() {
            container.innerHTML = `
                <div class="gallery-empty">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14zm-5.04-6.71l-2.75 3.54-1.96-2.36L6.5 17h11l-3.54-4.71z"/>
                    </svg>
                    <span>No artworks yet. Check back soon!</span>
                </div>
            `;
        }
    </script>
</body>
</html>
"""