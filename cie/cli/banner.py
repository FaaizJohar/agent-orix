"""
Agent Orix Terminal Banner & ASCII Art.
Provides compact, full, and gradient banners with Rich formatting and ANSI truecolor support.
"""

from typing import List, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align

# Custom AGENT ORIX ASCII Art Logo
AGENT_ORIX_ASCII: List[str] = [
    ".eeeeee...eeeeee..eeeeee.eeeeeee..eeeeeeeee.....eeeeee..eeeeeee..eee.eee..eee....",
    "@@@@@@@@:@@@@@@@@:@@@@@@:@@@@@@@@:@@@@@@@@@::::@@@@@@@@:@@@@@@@@:@@@:@@@::@@@::::",
    "%%%--%%%-%%%------%%%----%%%--%%%----%%%-------%%%--%%%-%%%--%%%-%%%-%%%--%%%----",
    "&&&&&&&&+&&&++++++&&&&&++&&&++&&&++++&&&+++++++&&&++&&&+&&&&&&&++&&&++&&&&&&+++++",
    "||||||||*|||*||||*|||||**|||**|||****|||*******|||**|||*||||||***|||**||||||*****",
    "!!!==!!!=!!!==!!!=!!!====!!!==!!!====!!!=======!!!==!!!=!!!=!!!==!!!=!!!==!!!====",
    ":::##:::#::::::::#::::::#:::##:::####:::#######::::::::#:::##:::#:::#:::##:::####",
    "...@@...@@......@@......@...@@...@@@@...@@@@@@@@......@@...@@...@...@...@@...@@@@",
]

# Legacy compact banner fallback for narrow viewports
COMPACT_BANNER: str = "\n".join(AGENT_ORIX_ASCII)

# Subtitle and metadata
AGENT_SUBTITLE = "Agent Orix — Interactive Terminal AI & Multi-Action Engine"
AGENT_MASCOT_URL = "https://files.catbox.moe/r1sys4.png"

# Smooth diagonal gradient color stops: Electric Cyan -> Sky Blue -> Neon Purple -> Hot Pink
GRADIENT_STOPS: List[Tuple[int, int, int]] = [
    (0, 240, 255),    # Electric Cyan (#00F0FF)
    (59, 130, 246),   # Bright Sky Blue (#3B82F6)
    (147, 51, 234),   # Neon Purple (#9333EA)
    (236, 72, 153),   # Hot Magenta / Pink (#EC4899)
]

FULL_MASCOT_ART = r"""
                                              =-:::::-                                         
                                        --:::::::.........::-                                  
                                     =::::::::::::::...........=                               
                      =-          -:::----::::::::::::............-                            
                       =-==-:::::::-=--:::--::::::::::::.............-                         
                         -:+*##*-:.....:=-:----::::::::::...............-                      
                         -::**##%%=.::::::+:-----:::::::::...:-+*###**+=:::                    
                       -.:::*###%%%+:::::::------:::::::::-+###%@@@@%#*++=-::-                 
                     -.:::-:*##%%@#%-::::::------::::::-+##**+++++*#@@#*++=-:-:                
                  -.:::::=-=##%#*@@@+::::::-----:::::=*+=++***+=-:..:-#%++==-.:::              
               +::::::--+*:##*+%@@@@=:::::=----:::-#@@@@@@@@@@@@@@@@%#::+*==-:::::             
             :::::---=+**=**=%%%@@#=-::::::---::-%@@@%%%#######***++++#%*:==--.::::            
          -::::----=+****==+%%%%%===:::::----:=%@@@@@@@%%%%%%%####***++-=#+---.::::-           
        -::----====+++++==#%%%%*--==::::---:-%@@@@@@@@@@@@%%%%%%#####**+=-#+--:....:           
      +-+    =::::--==++++%%%*:-----::::::-%@@@@@@@@@@@@@@@%%%%%%%*++##**=#%=-:....:           
                 =:::-===#%#:-----=-::::-%@@@@@@@@@@@@@@@@@@@%%%%#:..-####%*#.:....:           
                    :.::=*=:------=:::-#@@@@@%%%@@@@@@@@@@@@@@@%%#:...+##%%##-.:...:           
                      :.:::------=-::*@@@@@%=...+%@@@@@@@@@@@@@@%%=...:#%@@%#+.::::            
                      =:::------==::%@@@@@@#....:#@@@@@@@@@@@@@@%%#....#%@@%#*.::::            
                     -::-------==--@@@@@@@@%-....*%@@@@@@@@@@@@@@%%+..-%%@%%#+.:::    %%%      
                     ::----===+==-=@@@@@@@@%*....=%@@@@@@@@%%++%@@@%%#%%@%%#%:.::  %##%%*+*    
                     :---====*===:=%%%%@@@@@%=...*%@@@@#-:::=%%@@@@@@@@%%%*%=.::  =#%#****#    
                     ---====+@===::-%#+*%%@@@%%%%@@@@@@@@@@@@@@@@@@@%%%##%*..:- =:.::::::..:+  
                      =-====#@%===:.:-%%-=*#%%@@@@@@@@@@@@@@@@%%%%##%@*:...:: -.+=-----::::.:  
                        --===*@@#==-::::-==#%%@@@%%%%%%@@@@@%#+---::::::---=:..-#%=-----::::.+ 
      =::::=               ---==+**#==--::-================----------------::::+%%@=-----::::  
  +---:::::::..::              ==+=-=========---::::----=++++====+**:+=-+*----::#%%==-----::=  
 *%%%%@%*::::::::..:-         *#*=:-=***#*=+++*++=---:::::::::+#%%@=.=-%%=-----:-#+-==-----    
+%%%%@@@@@*:::::::::..:::.-=-:.:-==+***+======+#%%+===+++=--::.......-#@@+=====--:-+----=      
=#%%%@@%%%%%%-::::::::::::::--=====++-----=++=--:-.+#--::::::*@@@*:....-%@#======----:-         
+%%%@%%@@@@@%%=::::::::::::::------+#+-::::::=@@@#:.#=:::::-%%-:=:+*:...=+*%%*--::-=            
*#%%%###%%%%%@@*--::::--------=#%*-::::.......-@%@*:%+:::::-%#:#%#+++...-+==--:-                
+##--= -::=#%%%%%#=:::::=*#%%%%=:::::::.......:@@%-#%---::::*%+-*#-++...:%#-::                  
=+=        ::=#%%%@@%#%%%%@%%#::::::::::.....:+%%%@*-----::::-#%#*#*:...:%%*                    
            -:=#%%@@@@%%%%%+:*###%#*-:::::..-##*=----------::::::::....-++:                    
              -.-#%%%@@@@@%*-----:.+##-::::=#*+======--------::::::::::.###                    
                -:.=#%%%%%%:-------+:#*::-##++#%%%+===---------::::::-:.-                      
                    ----:-#--====-#%++=-*+==----:-%%*===--------::::*::.:                      
                      -:=%%#-=====@%##%#===-----:::+%%======------+*:::.-                      
                      -=%%%%%#=====+%%%-===------:--*@*======---**=-::==                       
                      =%%%%%%       #%#---===--------%#---=--=*+==--=#--                       
                      +%%%           ##=#:-===-------=*-==++++===-=#%=+                        
                      #                =#%-:-==-------   -======*%%+-+                         
                                        =%%*.-==-----    --======--+                           
                                         =#%%--==--=       =----=                              
                                         +===+===-=                                            
                                           +=====                                              
"""


def get_gradient_ascii_text(stops: Optional[List[Tuple[int, int, int]]] = None) -> Text:
    """
    Renders the Agent Orix ASCII logo with a smooth diagonal RGB gradient.
    """
    active_stops = stops or GRADIENT_STOPS
    styled = Text()
    num_rows = len(AGENT_ORIX_ASCII)
    max_cols = max(len(line) for line in AGENT_ORIX_ASCII)

    for r_idx, line in enumerate(AGENT_ORIX_ASCII):
        for c_idx, ch in enumerate(line):
            factor = (c_idx / max_cols) * 0.70 + (r_idx / num_rows) * 0.30
            factor = max(0.0, min(1.0, factor))
            n = len(active_stops) - 1
            idx = int(factor * n)
            if idx >= n:
                rgb = active_stops[-1]
            else:
                local_t = (factor * n) - idx
                c1, c2 = active_stops[idx], active_stops[idx + 1]
                rgb = (
                    int(c1[0] + (c2[0] - c1[0]) * local_t),
                    int(c1[1] + (c2[1] - c1[1]) * local_t),
                    int(c1[2] + (c2[2] - c1[2]) * local_t),
                )
            hex_col = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            styled.append(ch, style=f"bold {hex_col}")
        styled.append("\n")
    return styled


def get_gradient_ascii_ansi(stops: Optional[List[Tuple[int, int, int]]] = None) -> str:
    """
    Returns ANSI 24-bit truecolor formatted string of the ASCII logo.
    """
    active_stops = stops or GRADIENT_STOPS
    lines: List[str] = []
    num_rows = len(AGENT_ORIX_ASCII)
    max_cols = max(len(line) for line in AGENT_ORIX_ASCII)

    for r_idx, line in enumerate(AGENT_ORIX_ASCII):
        row_str = ""
        for c_idx, ch in enumerate(line):
            factor = (c_idx / max_cols) * 0.70 + (r_idx / num_rows) * 0.30
            factor = max(0.0, min(1.0, factor))
            n = len(active_stops) - 1
            idx = int(factor * n)
            if idx >= n:
                r, g, b = active_stops[-1]
            else:
                local_t = (factor * n) - idx
                c1, c2 = active_stops[idx], active_stops[idx + 1]
                r = int(c1[0] + (c2[0] - c1[0]) * local_t)
                g = int(c1[1] + (c2[1] - c1[1]) * local_t)
                b = int(c1[2] + (c2[2] - c1[2]) * local_t)
            row_str += f"\033[38;2;{r};{g};{b}m\033[1m{ch}\033[0m"
        lines.append(row_str)
    return "\n".join(lines)


def render_banner(
    console: Console,
    compact: bool = True,
    show_mascot: bool = False,
    version: str = "1.0.0",
    model_name: str = "cavrix-code:latest",
    tools_count: int = 46,
    remote_url: Optional[str] = None,
) -> None:
    """
    Renders styled banner to the provided Rich console.
    """
    if show_mascot:
        console.print(Text(FULL_MASCOT_ART, style="cyan dim"))

    # Render custom AGENT ORIX logo with 24-bit truecolor gradient
    banner_text = get_gradient_ascii_text()
    console.print(banner_text)

    mode_label = f"Remote: {remote_url}" if remote_url else f"Local Engine: {model_name}"
    info_line = (
        f"[bold white]Agent Orix[/bold white] [dim]v{version}[/dim] | "
        f"[cyan]{mode_label}[/cyan] | "
        f"[green]{tools_count} Tools[/green] | "
        f"[magenta]3 Workflows[/magenta]"
    )
    tips_line = (
        "[dim]Type your request naturally, or use [/dim][bold cyan]/help[/bold cyan][dim] for shortcuts.[/dim]"
    )

    panel = Panel(
        Align.center(f"{info_line}\n{tips_line}"),
        border_style="cyan dim",
        padding=(0, 2),
    )
    console.print(panel)
