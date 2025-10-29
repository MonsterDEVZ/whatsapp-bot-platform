"""
0:5B tenant_handlers - <>4C;L=0O A8AB5<0 >1@01>B:8 A>>1I5=89 4;O :064>3> 0@5=40B>@0.

064K9 0@5=40B>@ 8<55B A2>9 A>1AB25==K9 <>4C;L->1@01>BG8:, GB> >15A?5G8205B:
- 7>;OF8N ;>38:8 <564C 0@5=40B>@0<8
- 53:>ABL 4>102;5=8O =>2KE 0@5=40B>@>2
- >7<>6=>ABL =57028A8<>3> @0728B8O DC=:F8>=0;0

;O 4>102;5=8O =>2>3> 0@5=40B>@0:
1. !>7409B5 D09; {tenant_slug}_handler.py
2.  50;87C9B5 DC=:F8N handle_{tenant_slug}_menu()
3. >102LB5 8<?>@B 8 @538AB@0F8N 2 TENANT_MENU_HANDLERS
"""

from . import evopoliki_handler
from . import five_deluxe_handler

__all__ = ["evopoliki_handler", "five_deluxe_handler"]
