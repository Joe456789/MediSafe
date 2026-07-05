import json

class UserProfileMCPServer:
    """
    A simulated Model Context Protocol (MCP) server.
    Exposes the 'mcp://user/profile' resource containing patient allergies and active medications.
    """
    def __init__(self):
        # Mock data representing local user profile state
        self.profile = {
            "name": "John Doe",
            "allergies": ["Aspirin", "Penicillin"],
            "current_medications": ["Lisinopril"]
        }

    def list_resources(self) -> dict:
        """Exposes available resources, mimicking the MCP specification."""
        return {
            "resources": [
                {
                    "uri": "mcp://user/profile",
                    "name": "User Health Profile",
                    "mimeType": "application/json",
                    "description": "Patient's allergic history and current medications."
                }
            ]
        }

    def read_resource(self, uri: str) -> dict:
        """Reads a resource by URI, mimicking the MCP specification."""
        if uri == "mcp://user/profile":
            return {
                "contents": [
                    {
                        "uri": "mcp://user/profile",
                        "mimeType": "application/json",
                        "text": json.dumps(self.profile, indent=2)
                    }
                ]
            }
        raise ValueError(f"Resource not found: {uri}")

if __name__ == "__main__":
    import sys
    server = UserProfileMCPServer()
    
    # Read line-by-line from stdin
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})
            
            if method == "resources/list":
                res = {
                    "jsonrpc": "2.0",
                    "result": server.list_resources(),
                    "id": req_id
                }
            elif method == "resources/read":
                uri = params.get("uri")
                try:
                    read_res = server.read_resource(uri)
                    res = {
                        "jsonrpc": "2.0",
                        "result": read_res,
                        "id": req_id
                    }
                except Exception as e:
                    res = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32602, "message": str(e)},
                        "id": req_id
                    }
            else:
                res = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": req_id
                }
            
            # Print response to stdout and flush immediately
            print(json.dumps(res))
            sys.stdout.flush()
        except Exception as e:
            err_res = {
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
                "id": None
            }
            print(json.dumps(err_res))
            sys.stdout.flush()

