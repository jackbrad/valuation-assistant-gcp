"""Reset demo state to baseline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.state import state
import data_gen.generator as generator
import data_gen.pdf_generator as pdf_gen


def reset_demo():
    print("Resetting Appraisal AI Demo state to baseline...")
    # Re-run generator and pdf generation
    generator.main()
    pdf_gen.generate_demo_pdfs()
    
    # Reload state
    global state
    from app.state import DemoState
    state = DemoState()
    print("Demo state successfully reset to initial baseline.")
    print("14 Larkspur Ln: GLA restored to 1,240 SF (stale public record).")
    print("Review queue: 22 Hilltop Rd G1 conflict pending.")
    print("Circuit breaker: Riverside tightened, others normal.")


if __name__ == "__main__":
    reset_demo()
