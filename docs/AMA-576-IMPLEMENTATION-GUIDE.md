# AMA-576: Implementation Guide
## Quick-Start Reference for AI Integration Development

---

## Phase 1: MCP Server Implementation (Weeks 1-2)

### Quick Start

```bash
# Create new repository
mkdir mcp-mapper-api
cd mcp-mapper-api
npm init -y
npm install @modelcontextprotocol/sdk axios typescript ts-node @types/node

# Create structure
mkdir -p src/{tools,resources,config}
touch src/index.ts src/server.ts src/tools/{exercises,workouts,mappings}.ts
```

### Core Tools Reference

#### Tool 1: suggest_exercise
```typescript
{
  "name": "suggest_exercise",
  "description": "Get canonical exercise match for raw exercise name",
  "input": {
    "exercise_name": "string (required)",
    "include_similar_types": "boolean (optional, default: true)"
  },
  "endpoint": "POST /exercise/suggest",
  "example_request": {
    "exercise_name": "SOME TYPE OF SQUAT",
    "include_similar_types": true
  },
  "example_response": {
    "best_match": {"name": "Squat", "score": 0.95},
    "similar_exercises": [...],
    "exercises_by_type": [...],
    "category": "squat"
  }
}
```

#### Tool 2: find_similar_exercises
```typescript
{
  "name": "find_similar_exercises",
  "description": "Find exercises similar to input name",
  "input": {
    "exercise_name": "string (required)",
    "limit": "number (optional, default: 10)"
  },
  "endpoint": "GET /exercise/similar/{name}?limit={limit}",
  "example_response": {
    "exercise_name": "BENCH PRESS",
    "similar": [
      {"name": "Bench Press", "score": 1.0},
      {"name": "Dumbbell Bench Press", "score": 0.92}
    ]
  }
}
```

#### Tool 3: find_exercises_by_type
```typescript
{
  "name": "find_exercises_by_type",
  "description": "Find all exercises of same type (e.g., all squats)",
  "input": {
    "exercise_name": "string (required)",
    "limit": "number (optional, default: 20)"
  },
  "endpoint": "GET /exercise/by-type/{name}?limit={limit}",
  "example_response": {
    "exercise_name": "SQUAT",
    "category": "squat",
    "exercises": [
      {"name": "Squat", "score": 1.0},
      {"name": "Air Squat", "score": 0.95},
      {"name": "Back Squat", "score": 0.90}
    ]
  }
}
```

#### Tool 4: add_user_mapping
```typescript
{
  "name": "add_user_mapping",
  "description": "Add custom mapping from raw to canonical exercise name",
  "input": {
    "raw_name": "string (required)",
    "canonical_name": "string (required)"
  },
  "endpoint": "POST /mapping/add",
  "example_request": {
    "raw_name": "MY SQUAT VARIATION",
    "canonical_name": "Squat"
  },
  "example_response": {
    "status": "success",
    "mapping": {"raw": "MY SQUAT VARIATION", "canonical": "Squat"}
  }
}
```

#### Tool 5: remove_user_mapping
```typescript
{
  "name": "remove_user_mapping",
  "description": "Remove custom user mapping",
  "input": {
    "raw_name": "string (required)"
  },
  "endpoint": "DELETE /mapping/{raw_name}",
  "example_response": {
    "status": "success",
    "removed": "MY SQUAT VARIATION"
  }
}
```

#### Tool 6: list_user_mappings
```typescript
{
  "name": "list_user_mappings",
  "description": "List all user's custom mappings",
  "input": {},
  "endpoint": "GET /mapping/list",
  "example_response": {
    "mappings": [
      {"raw": "MY SQUAT", "canonical": "Squat"},
      {"raw": "DB PRESS", "canonical": "Dumbbell Bench Press"}
    ],
    "count": 2
  }
}
```

#### Tool 7: create_workout
```typescript
{
  "name": "create_workout",
  "description": "Create a new workout with exercises",
  "input": {
    "exercises": "object[] (required) - [{name, reps, sets, weight}]",
    "duration_minutes": "number (optional)",
    "calories": "number (optional)",
    "notes": "string (optional)"
  },
  "endpoint": "POST /workout/create",
  "example_request": {
    "exercises": [
      {"name": "Squat", "reps": 10, "sets": 3, "weight": 185},
      {"name": "Bench Press", "reps": 8, "sets": 4, "weight": 225}
    ],
    "duration_minutes": 45,
    "calories": 250
  },
  "example_response": {
    "workout_id": "wkt_123abc",
    "created_at": "2025-02-15T14:45:00Z",
    "exercise_count": 2
  }
}
```

#### Tool 8: export_garmin_yaml
```typescript
{
  "name": "export_garmin_yaml",
  "description": "Export workout as Garmin YAML format",
  "input": {
    "workout_id": "string (required)"
  },
  "endpoint": "GET /workout/{workout_id}/export/garmin",
  "example_response": {
    "format": "yaml",
    "content": "# Garmin Workout YAML...\nexercise_1:\n  name: Squat\n  reps: 10\n  sets: 3"
  }
}
```

### Example Claude Desktop Config

**File:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mapper-api": {
      "command": "node",
      "args": [
        "/Users/david/projects/mcp-mapper-api/dist/index.js"
      ],
      "env": {
        "MAPPER_API_URL": "http://localhost:8000",
        "API_KEY": "your-api-key-here",
        "DEBUG": "true"
      }
    }
  }
}
```

### Example VS Code MCP Config

**File:** `.vscode/settings.json`

```json
{
  "modelContextProtocol.servers": [
    {
      "name": "mapper-api",
      "command": "node",
      "args": ["/path/to/mcp-mapper-api/dist/index.js"],
      "env": {
        "MAPPER_API_URL": "http://localhost:8000",
        "API_KEY": "sk-1234567890"
      }
    }
  ]
}
```

### Example Cursor IDE Setup

Cursor has built-in MCP support (beta). Add to `.cursor/mcp_servers.json`:

```json
[
  {
    "name": "mapper-api",
    "command": "node",
    "args": ["/path/to/mcp-mapper-api/dist/index.js"],
    "env": {
      "MAPPER_API_URL": "http://localhost:8000",
      "API_KEY": "your-api-key"
    }
  }
]
```

### Testing Checklist

- [ ] Start mapper-api server: `uvicorn backend.app:app --reload`
- [ ] Start MCP server: `node dist/index.js`
- [ ] Test Claude Desktop connection
- [ ] Test VS Code connection
- [ ] Test all 8 tools with sample inputs
- [ ] Test error handling (missing required params)
- [ ] Test authentication (valid & invalid API keys)
- [ ] Test timeout handling (long-running requests)

---

## Phase 2: Chrome Extension Implementation (Weeks 3-5)

### Quick Start

```bash
mkdir mcp-mapper-extension
cd mcp-mapper-extension

# Create manifest & structure
mkdir -p {src/{content,background,popup},dist,public}
touch manifest.json src/{content,background,popup}/index.ts
```

### Manifest v3 Template

**manifest.json:**
```json
{
  "manifest_version": 3,
  "name": "Mapper Exercise Normalizer",
  "version": "1.0.0",
  "description": "Normalize exercise names with AI assistance",
  "permissions": [
    "scripting",
    "contextMenus",
    "storage"
  ],
  "host_permissions": [
    "https://*.garmin.com/*",
    "https://*.applehealth.com/*"
  ],
  "action": {
    "default_popup": "popup/index.html",
    "default_title": "Exercise Mapper"
  },
  "icons": {
    "16": "images/icon-16.png",
    "48": "images/icon-48.png",
    "128": "images/icon-128.png"
  },
  "background": {
    "service_worker": "background/index.js"
  },
  "content_scripts": [
    {
      "matches": ["https://*.garmin.com/*", "https://*.applehealth.com/*"],
      "js": ["content/index.js"],
      "run_at": "document_start"
    }
  ]
}
```

### Context Menu Handler

**src/background/index.ts:**
```typescript
// Add context menu for exercise names
chrome.contextMenus.create({
  id: "map-exercise",
  title: "Map This Exercise",
  contexts: ["selection"]
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "map-exercise" && tab?.id) {
    const selectedText = info.selectionText || "";
    
    // Send to MCP server
    fetch("http://localhost:3000/tools/suggest_exercise", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exercise_name: selectedText })
    })
    .then(r => r.json())
    .then(data => {
      // Send result back to content script
      chrome.tabs.sendMessage(tab.id, {
        action: "show_suggestion",
        suggestion: data.best_match
      });
    });
  }
});
```

### Content Script (DOM Integration)

**src/content/index.ts:**
```typescript
// Listen for suggestions from background script
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === "show_suggestion") {
    // Create floating suggestion widget
    const widget = document.createElement("div");
    widget.id = "mapper-suggestion-widget";
    widget.innerHTML = `
      <div style="
        position: fixed; bottom: 20px; right: 20px;
        background: white; border: 1px solid #ccc;
        padding: 15px; border-radius: 8px; z-index: 10000;
      ">
        <strong>${message.suggestion.name}</strong>
        <div style="font-size: 0.9em; color: #666;">
          Score: ${(message.suggestion.score * 100).toFixed(0)}%
        </div>
        <button id="mapper-apply">Apply</button>
        <button id="mapper-close">Close</button>
      </div>
    `;
    
    document.body.appendChild(widget);
    
    document.getElementById("mapper-apply")?.addEventListener("click", () => {
      // Apply the mapping to the page
      // (implementation depends on target website)
      widget.remove();
    });
    
    document.getElementById("mapper-close")?.addEventListener("click", () => {
      widget.remove();
    });
  }
});
```

### Popup UI (HTML)

**src/popup/index.html:**
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="container">
    <h2>🏋️ Exercise Mapper</h2>
    
    <div class="input-group">
      <input 
        type="text" 
        id="exercise-input" 
        placeholder="Enter exercise name..."
        autocomplete="off"
      />
    </div>
    
    <div id="suggestions" class="suggestions-list"></div>
    
    <div class="settings">
      <button id="settings-btn">⚙️ Settings</button>
    </div>
  </div>
  
  <script src="index.js"></script>
</body>
</html>
```

**src/popup/styles.css:**
```css
body {
  width: 400px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
  margin: 0;
  padding: 10px;
}

.container {
  padding: 10px;
}

.input-group {
  margin: 10px 0;
}

input[type="text"] {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box;
}

.suggestions-list {
  margin-top: 15px;
  max-height: 300px;
  overflow-y: auto;
}

.suggestion-item {
  padding: 8px;
  border: 1px solid #eee;
  border-radius: 4px;
  margin: 5px 0;
  cursor: pointer;
  transition: background 0.2s;
}

.suggestion-item:hover {
  background: #f5f5f5;
}

.suggestion-name {
  font-weight: 500;
}

.suggestion-score {
  font-size: 0.9em;
  color: #666;
}

.settings {
  margin-top: 15px;
  padding-top: 10px;
  border-top: 1px solid #eee;
}

button {
  padding: 6px 12px;
  background: #0066cc;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

button:hover {
  background: #0052a3;
}
```

### Testing Checklist

- [ ] Manifest validates (no errors)
- [ ] Context menu appears in browser
- [ ] WebSocket connects to MCP server
- [ ] Suggestions display in popup
- [ ] DOM interactions work (click, type)
- [ ] Settings persist (localStorage)
- [ ] Tested on Chrome, Edge, Brave
- [ ] No console errors
- [ ] Performance is smooth

---

## Testing & Validation

### Unit Tests (MCP)

```bash
npm install --save-dev jest @types/jest ts-jest

# In jest.config.js
export default {
  preset: "ts-jest",
  testEnvironment: "node",
  testMatch: ["**/__tests__/**/*.test.ts"]
};
```

**Example test:**
```typescript
// __tests__/tools/exercises.test.ts
import { handleSuggestExercise } from "../../src/tools/exercises";

describe("suggest_exercise", () => {
  it("returns best match for squat", async () => {
    const result = await handleSuggestExercise({
      exercise_name: "SOME TYPE OF SQUAT"
    });
    
    expect(result.best_match).toBeDefined();
    expect(result.best_match.name).toBe("Squat");
    expect(result.best_match.score).toBeGreaterThan(0.8);
  });
  
  it("returns empty on invalid input", async () => {
    const result = await handleSuggestExercise({
      exercise_name: "xyzabc"
    });
    
    expect(result.needs_user_search).toBe(true);
  });
});
```

### Integration Tests (End-to-End)

```bash
# Start mapper-api
cd /path/to/mapper-api
uvicorn backend.app:app

# Start MCP server
node dist/index.js

# Run Claude Desktop tests
npm run test:claude
```

---

## Deployment

### MCP Server Deployment

**Option 1: npm Registry (Recommended)**
```bash
npm login
npm publish

# Users install with:
npm install @supergeri/mcp-mapper-api
```

**Option 2: GitHub Releases**
```bash
# Create release on GitHub
# Users install with:
npm install github:supergeri/mcp-mapper-api
```

**Option 3: Direct Installation**
```bash
# Users clone and install:
git clone https://github.com/supergeri/mcp-mapper-api
cd mcp-mapper-api
npm install
npm run build
```

### Chrome Extension Deployment

1. Prepare assets:
   - Extension icons (16x16, 48x48, 128x128 PNG)
   - Store listing images (1280x800 PNG)
   - Privacy policy document

2. Create Chrome Web Store listing:
   - Name, description, category
   - Screenshots & promotional images
   - Privacy policy (required)
   - Support contact email

3. Submit:
   - Upload .zip file (src + dist)
   - Pay $5 developer fee (one-time)
   - Await review (24-72 hours)

4. After approval:
   - Share store link
   - Monitor ratings & reviews
   - Push updates as needed

---

## Success Metrics & KPIs

### Phase 1: MCP Server

**Weeks 1-2:**
- [ ] MVP shipped on npm & GitHub
- [ ] Documentation complete
- [ ] Works with Claude Desktop, VS Code, Cursor
- [ ] All tools functional

**Months 1-3:**
- [ ] 100+ npm installs
- [ ] 20+ GitHub stars
- [ ] 10+ early users providing feedback
- [ ] < 0.5% error rate
- [ ] Response time < 500ms

### Phase 2: Chrome Extension

**Weeks 3-5:**
- [ ] Extension submitted to Chrome Web Store
- [ ] Beta testing with 5-10 power users
- [ ] All features working

**Months 1-3:**
- [ ] 100+ installations
- [ ] 4.0+ star rating
- [ ] < 5% uninstall rate
- [ ] Positive user reviews

---

## Troubleshooting

### MCP Server Issues

| Issue | Solution |
|-------|----------|
| Can't connect to mapper-api | Check MAPPER_API_URL is correct, mapper-api is running |
| 401 Unauthorized | Verify API_KEY is valid |
| Timeout errors | Increase timeout, check network |
| Tool not found | Verify tool name in MCP config |

### Chrome Extension Issues

| Issue | Solution |
|-------|----------|
| Extension not loading | Check manifest.json syntax, reload extension |
| WebSocket connection fails | Verify MCP server is running, check port |
| DOM operations don't work | Check content_scripts match pattern in manifest |
| Settings not saving | Check localStorage permissions in manifest |

---

**Ready to start building? Begin with Phase 1 (MCP Server)!**
