# Homebrew formula for drift-analyzer.
#
# This formula is maintained in the drift repository for reference.
# To submit to homebrew-core, the project needs ≥75 stars, ≥30 forks
# or notable adoption. Until then, use the tap:
#
#   brew tap mick-gsk/drift https://github.com/mick-gsk/drift
#   brew install drift-analyzer
#
# Or install directly via pipx (recommended):
#   pipx install drift-analyzer

class DriftAnalyzer < Formula
  include Language::Python::Virtualenv

  desc "Catches structural erosion from AI-generated code that passes all your tests"
  homepage "https://github.com/mick-gsk/drift"
  url "https://pypi.io/packages/source/d/drift-analyzer/drift_analyzer-2.5.1.tar.gz"
  # sha256 "UPDATE_WITH_REAL_SHA256"
  license "MIT"

  depends_on "python@3.13"

  resource "click" do
    url "https://pypi.io/packages/source/c/click/click-8.1.8.tar.gz"
    # sha256 "UPDATE"
  end

  resource "rich" do
    url "https://pypi.io/packages/source/r/rich/rich-13.9.4.tar.gz"
    # sha256 "UPDATE"
  end

  resource "pyyaml" do
    url "https://pypi.io/packages/source/p/pyyaml/pyyaml-6.0.2.tar.gz"
    # sha256 "UPDATE"
  end

  resource "pydantic" do
    url "https://pypi.io/packages/source/p/pydantic/pydantic-2.10.6.tar.gz"
    # sha256 "UPDATE"
  end

  resource "gitpython" do
    url "https://pypi.io/packages/source/g/gitpython/gitpython-3.1.44.tar.gz"
    # sha256 "UPDATE"
  end

  resource "networkx" do
    url "https://pypi.io/packages/source/n/networkx/networkx-3.4.2.tar.gz"
    # sha256 "UPDATE"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/drift --version")
    assert_match "Usage", shell_output("#{bin}/drift --help")
  end
end
