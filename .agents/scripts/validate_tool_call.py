import sys
import json
import shlex
import os

def main():
    try:
        # Load the tool invocation context from stdin
        context = json.load(sys.stdin)
        command = context.get("tool_args", {}).get("CommandLine", "")
        cwd = context.get("tool_args", {}).get("Cwd", os.getcwd())
        
        # Parse command structurally into shell tokens
        try:
            tokens = shlex.split(command)
        except Exception:
            tokens = command.split()
            
        if not tokens:
            print("APPROVED: Empty command.", file=sys.stderr)
            sys.exit(0)
            
        executable = os.path.basename(tokens[0].lower()).replace(".exe", "")
        
        # 1. Block destructive binaries
        blocked_binaries = ["rm", "del", "mkfs", "format", "rd", "rmdir", "nuke"]
        if executable in blocked_binaries:
            print(f"BLOCKED: Dangerous binary '{executable}' execution forbidden.", file=sys.stderr)
            sys.exit(1)
            
        # 2. Block Command Chaining (&&, ||, ;, |) to prevent command injection escapes
        chain_symbols = [";", "&&", "||", "|"]
        for sym in chain_symbols:
            if sym in tokens or sym in command:
                print(f"BLOCKED: Command chaining operator '{sym}' is forbidden in sandbox environment.", file=sys.stderr)
                sys.exit(1)
                
        # 3. Path Traversal & Sandbox Escape Check
        workspace_dir = os.path.abspath(cwd)
        for tok in tokens[1:]:
            if ".." in tok or tok.startswith("/") or (len(tok) > 1 and tok[1] == ":"):
                normalized_path = os.path.abspath(os.path.join(workspace_dir, tok))
                # Check if resolved path is outside the workspace directory
                if not normalized_path.startswith(workspace_dir):
                    print(f"BLOCKED: Path traversal escape detected: '{tok}' resolves outside the workspace.", file=sys.stderr)
                    sys.exit(1)

        print("APPROVED: Command validation passed structural check.")
        sys.exit(0)
    except Exception as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
