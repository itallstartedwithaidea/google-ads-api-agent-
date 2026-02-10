import json
import time
from datetime import datetime

def safe_install_and_import(package_spec, import_name=None, from_import=None):
    """
    Attempts to install and import a package safely.

    Args:
        package_spec: Full pip spec like 'mpmath>=1.3.0'
        import_name: Module name to import (if different from package)
        from_import: Specific item to import from module

    Returns:
        tuple: (success: bool, module_or_error: module|str)
    """
    if import_name is None:
        import_name = package_spec.split('>=')[0].split('==')[0].split('[')[0].replace('-', '_')

    try:
        if from_import:
            mod = __import__(import_name, fromlist=[from_import])
            return (True, mod)
        else:
            return (True, __import__(import_name))
    except ImportError:
        pass

    try:
        import pip
        pip.main(['install', package_spec, '--quiet', '--disable-pip-version-check'])

        if from_import:
            mod = __import__(import_name, fromlist=[from_import])
            return (True, mod)
        else:
            return (True, __import__(import_name))
    except Exception as e:
        return (False, str(e))


def run(install_category="all"):
    """
    Installs requested package categories and reports results.

    Args:
        install_category: "all", "math", "testing", "advertising", "presentation",
                         "html_css", "color_design", "persistence", or "financial"

    Returns:
        dict with installation results
    """

    start_time = time.time()
    results = {
        "status": "success",
        "requested_category": install_category,
        "timestamp": datetime.now().isoformat(),
        "packages": {},
        "summary": {
            "total": 0,
            "installed": 0,
            "failed": 0
        }
    }

    packages = {
        "math": [
            {"spec": "mpmath>=1.3.0", "import": "mpmath", "name": "mpmath"},
            {"spec": "gmpy2>=2.1.5", "import": "gmpy2", "name": "gmpy2"},
            {"spec": "uncertainties>=3.1.7", "import": "uncertainties", "name": "uncertainties"},
        ],
        "testing": [
            {"spec": "hypothesis>=6.92.0", "import": "hypothesis", "name": "hypothesis"},
            {"spec": "pytest>=7.4.3", "import": "pytest", "name": "pytest"},
        ],
        "advertising": [
            {"spec": "facebook-business>=19.0.0", "import": "facebook_business", "name": "facebook-business"},
            {"spec": "bingads>=13.0.18", "import": "bingads", "name": "bingads"},
            {"spec": "msal>=1.26.0", "import": "msal", "name": "msal"},
            {"spec": "google-analytics-data>=0.18.4", "import": "google.analytics.data", "name": "google-analytics-data"},
        ],
        "presentation": [
            {"spec": "python-pptx>=0.6.23", "import": "pptx", "name": "python-pptx"},
        ],
        "html_css": [
            {"spec": "jinja2>=3.1.2", "import": "jinja2", "name": "jinja2"},
            {"spec": "dominate>=2.9.1", "import": "dominate", "name": "dominate"},
            {"spec": "cssutils>=2.9.0", "import": "cssutils", "name": "cssutils"},
            {"spec": "css-inline>=0.11.0", "import": "css_inline", "name": "css-inline"},
            {"spec": "premailer>=3.10.0", "import": "premailer", "name": "premailer"},
            {"spec": "htmlmin>=0.1.12", "import": "htmlmin", "name": "htmlmin"},
        ],
        "color_design": [
            {"spec": "colour>=0.1.5", "import": "colour", "name": "colour"},
            {"spec": "colorthief>=0.2.1", "import": "colorthief", "name": "colorthief"},
            {"spec": "palettable>=3.3.3", "import": "palettable", "name": "palettable"},
        ],
        "persistence": [
            {"spec": "dill>=0.3.7", "import": "dill", "name": "dill"},
            {"spec": "cloudpickle>=3.0.0", "import": "cloudpickle", "name": "cloudpickle"},
            {"spec": "tinydb>=4.8.0", "import": "tinydb", "name": "tinydb"},
            {"spec": "diskcache>=5.6.3", "import": "diskcache", "name": "diskcache"},
        ],
        "financial": [
            {"spec": "pint>=0.23", "import": "pint", "name": "pint"},
            {"spec": "quantstats>=0.0.62", "import": "quantstats", "name": "quantstats"},
            {"spec": "lifetimes>=0.11.3", "import": "lifetimes", "name": "lifetimes"},
        ],
    }

    if install_category.lower() == "all":
        categories_to_install = list(packages.keys())
    elif install_category.lower() in packages:
        categories_to_install = [install_category.lower()]
    else:
        return {
            "status": "error",
            "message": f"Unknown category: {install_category}",
            "valid_categories": ["all"] + list(packages.keys())
        }

    for category in categories_to_install:
        results["packages"][category] = {}

        for pkg in packages[category]:
            pkg_start = time.time()
            results["summary"]["total"] += 1

            success, result = safe_install_and_import(
                pkg["spec"], 
                pkg["import"]
            )

            pkg_time = round(time.time() - pkg_start, 2)

            if success:
                results["summary"]["installed"] += 1
                try:
                    version = getattr(result, '__version__', 'unknown')
                except:
                    version = 'installed'

                results["packages"][category][pkg["name"]] = {
                    "status": "installed",
                    "version": version,
                    "install_time_sec": pkg_time
                }
            else:
                results["summary"]["failed"] += 1
                results["packages"][category][pkg["name"]] = {
                    "status": "failed",
                    "error": result[:200] if len(result) > 200 else result,
                    "install_time_sec": pkg_time
                }

    results["total_time_sec"] = round(time.time() - start_time, 2)
    results["summary"]["success_rate"] = f"{round(results['summary']['installed'] / max(results['summary']['total'], 1) * 100, 1)}%"

    results["available_imports"] = []
    for category, pkgs in results["packages"].items():
        for pkg_name, pkg_result in pkgs.items():
            if pkg_result["status"] == "installed":
                results["available_imports"].append(pkg_name)

    return results
