from flask import Flask, session, render_template, request, redirect, url_for
import pickle

app = Flask(__name__)
app.secret_key = "replace-this-with-a-secret-key"

class CPU:
    def __init__(self, lines):
        self.reg = {r: 0 for r in ["A", "B", "C", "D", "E", "H", "L"]}
        self.mem = [0] * 65536
        self.flags = {"Z": 0}
        self.code = []
        self.labels = {}
        self.pc = 0

        # Label preprocessing
        for line in lines:
            clean = line.strip()
            if not clean:
                continue
            if ':' in clean:
                label, rest = clean.split(':', 1)
                self.labels[label.strip()] = len(self.code)
                if rest.strip():
                    self.code.append(rest.strip())
            else:
                self.code.append(clean)

    def step(self):
        if self.pc < len(self.code):
            line = self.code[self.pc].strip()
            if not line:
                self.pc += 1
                return

            parts = line.split()
            op = parts[0].upper()
            args = parts[1:] if len(parts) > 1 else []

            def hl_addr():
                return (self.reg["H"] << 8) | self.reg["L"]

            def safe_int(s):
                try:
                    if s.lower().endswith("h"):
                        return int(s[:-1], 16)
                    return int(s.lstrip("0") or "0")
                except ValueError:
                    return 0

            if op == "MVI":
                dst = args[0].rstrip(",")
                val_str = args[1]
                val = safe_int(val_str)
                if dst == "M":
                    self.mem[hl_addr()] = val & 0xFF
                else:
                    self.reg[dst] = val & 0xFF

            elif op == "MOV":
                dst = args[0].rstrip(",")
                src = args[1]
                if dst == "M":
                    self.mem[hl_addr()] = self.reg[src]
                elif src == "M":
                    self.reg[dst] = self.mem[hl_addr()]
                else:
                    self.reg[dst] = self.reg[src]

            elif op == "ADD":
                src = args[0]
                val = self.mem[hl_addr()] if src == "M" else self.reg[src]
                self.reg["A"] = (self.reg["A"] + val) & 0xFF
                self.flags["Z"] = int(self.reg["A"] == 0)

            elif op == "INR":
                r = args[0]
                self.reg[r] = (self.reg[r] + 1) & 0xFF
                self.flags["Z"] = int(self.reg[r] == 0)

            elif op == "DCR":
                r = args[0]
                self.reg[r] = (self.reg[r] - 1) & 0xFF
                self.flags["Z"] = int(self.reg[r] == 0)

            elif op == "LXI":
                if args[0] == "H,":
                    addr = safe_int(args[1])
                    self.reg["H"] = (addr >> 8) & 0xFF
                    self.reg["L"] = addr & 0xFF

            elif op == "JMP":
                target = args[0]
                addr = self.labels.get(target)
                if addr is None:
                    addr = safe_int(target)
                self.pc = addr
                return

            elif op == "JNZ":
                target = args[0]
                addr = self.labels.get(target)
                if addr is None:
                    addr = safe_int(target)
                if self.flags["Z"] == 0:
                    self.pc = addr
                    return

            self.pc += 1

    def reset(self):
        self.pc = 0
        self.reg = {r: 0 for r in self.reg}
        self.mem = [0] * 65536
        self.flags = {"Z": 0}

def get_cpu():
    data = session.get("cpu")
    return pickle.loads(data) if data else None

def save_cpu(cpu):
    session["cpu"] = pickle.dumps(cpu)

@app.route("/", methods=["GET", "POST"])
def index():
    cpu = get_cpu()
    if (request.method == "POST" and "new_code" in request.form) or not cpu:
        raw = request.form.get("code", "")
        lines = [l for l in raw.splitlines() if l.strip()]
        cpu = CPU(lines)
        save_cpu(cpu)

    return render_template(
        "index.html",
        code_text="\n".join(cpu.code),
        pc=cpu.pc,
        regs=cpu.reg,
        mem=cpu.mem[:16]  # display first 16 memory addresses
    )

@app.route("/step", methods=["POST"])
def step():
    cpu = get_cpu()
    cpu.step()
    save_cpu(cpu)
    return redirect(url_for("index"))

@app.route("/run", methods=["POST"])
def run():
    cpu = get_cpu()
    while cpu.pc < len(cpu.code):
        cpu.step()
    save_cpu(cpu)
    return redirect(url_for("index"))

@app.route("/reset", methods=["POST"])
def reset():
    cpu = get_cpu()
    cpu.reset()
    save_cpu(cpu)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
