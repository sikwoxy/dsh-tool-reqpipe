"""支持 `python -m reqpipe` 运行。"""

import sys

from reqpipe.cli import main

if __name__ == "__main__":
    sys.exit(main())
