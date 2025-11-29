"""
Browser-based faucet claiming for DuckDice.

The faucet claiming API requires browser session authentication (cookies,
X-Fingerprint header) rather than API key authentication. This module uses
Playwright to automate the browser-based faucet claiming process.
"""
from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None
    Browser = None
    BrowserContext = None
    Page = None
    PlaywrightTimeout = None


@dataclass
class BrowserConfig:
    """Configuration for browser-based faucet claiming."""
    headless: bool = True
    timeout_ms: int = 30000
    user_data_dir: Optional[str] = None  # Path to persist browser session
    verbose: bool = False


@dataclass
class FaucetClaimResult:
    """Result of a browser-based faucet claim."""
    currency: str
    success: bool
    amount: str = "0"
    error: str = ""
    cooldown_remaining: int = 0


class BrowserFaucetClaimer:
    """
    Browser-based faucet claimer for DuckDice.
    
    Uses Playwright to automate the faucet claiming process through
    the actual website, bypassing Cloudflare protection.
    """
    
    BASE_URL = "https://duckdice.io"
    FAUCET_URL = "https://duckdice.io/dice?gameMode=faucet"
    
    def __init__(
        self,
        config: BrowserConfig,
        logger: Optional[Callable[[str], None]] = None,
    ):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is required for browser-based faucet claiming. "
                "Install it with: pip install playwright && playwright install chromium"
            )
        
        self.config = config
        self.logger = logger or print
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in = False
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.config.verbose:
            self.logger(message)
    
    def _ensure_browser(self) -> None:
        """Ensure browser is started."""
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self.config.headless,
            )
    
    def _ensure_context(self) -> BrowserContext:
        """Ensure browser context exists, creating if needed."""
        self._ensure_browser()
        
        if self._context is None:
            # Create context with persistent storage if configured
            context_options = {
                "viewport": {"width": 1280, "height": 720},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }
            
            if self.config.user_data_dir:
                # Use persistent context
                self._context = self._playwright.chromium.launch_persistent_context(
                    self.config.user_data_dir,
                    headless=self.config.headless,
                    **context_options,
                )
                # In persistent context, browser and context are the same
                self._browser = self._context
            else:
                self._context = self._browser.new_context(**context_options)
        
        return self._context
    
    def _ensure_page(self) -> Page:
        """Ensure page exists, creating if needed."""
        context = self._ensure_context()
        
        if self._page is None or self._page.is_closed():
            self._page = context.new_page()
            self._page.set_default_timeout(self.config.timeout_ms)
        
        return self._page
    
    def is_logged_in(self) -> bool:
        """Check if user is logged in."""
        page = self._ensure_page()
        
        try:
            # Navigate to the site if not already there
            if self.BASE_URL not in page.url:
                page.goto(self.BASE_URL, wait_until="networkidle")
            
            # Check for logged-in indicators
            # Look for user menu or balance display
            page.wait_for_timeout(2000)  # Wait for page to settle
            
            # Try to find login/register button (indicates NOT logged in)
            login_button = page.locator("button:has-text('Log In'), a:has-text('Log In')").first
            
            try:
                login_button.wait_for(timeout=3000)
                # Login button found = not logged in
                self._logged_in = False
                return False
            except PlaywrightTimeout:
                # Login button not found, likely logged in
                # Try to verify by looking for user-specific elements
                try:
                    # Look for balance or user menu
                    page.locator("[data-testid='user-balance'], .user-balance, .balance").first.wait_for(timeout=3000)
                    self._logged_in = True
                    return True
                except PlaywrightTimeout:
                    # Can't determine, assume logged in if no login button
                    self._logged_in = True
                    return True
                    
        except Exception as e:
            self.log(f"Error checking login status: {e}")
            return False
    
    def wait_for_login(self, timeout_sec: int = 300) -> bool:
        """
        Wait for user to manually log in.
        
        Opens the browser in non-headless mode and waits for the user
        to complete the login process.
        
        Args:
            timeout_sec: Maximum seconds to wait for login
            
        Returns:
            True if login successful, False if timeout
        """
        # Force non-headless for manual login
        was_headless = self.config.headless
        if was_headless:
            self.log("Opening browser for manual login...")
            self.close()
            self.config.headless = False
        
        page = self._ensure_page()
        
        try:
            page.goto(self.BASE_URL, wait_until="networkidle")
            
            self.log(f"Please log in to DuckDice in the browser window...")
            self.log(f"Waiting up to {timeout_sec} seconds for login...")
            
            start_time = time.time()
            while (time.time() - start_time) < timeout_sec:
                if self.is_logged_in():
                    self.log("Login detected!")
                    return True
                time.sleep(2)
            
            self.log("Login timeout reached.")
            return False
            
        finally:
            # Restore headless setting
            self.config.headless = was_headless
    
    def claim_faucet(self, currency: str) -> FaucetClaimResult:
        """
        Claim faucet for a specific currency using browser automation.
        
        Args:
            currency: Currency symbol (e.g., 'sol', 'btc')
            
        Returns:
            FaucetClaimResult with claim outcome
        """
        result = FaucetClaimResult(
            currency=currency.upper(),
            success=False,
        )
        
        if not self._logged_in and not self.is_logged_in():
            result.error = "Not logged in. Please run with --login first."
            return result
        
        page = self._ensure_page()
        
        try:
            # Navigate to faucet page
            self.log(f"Navigating to faucet page...")
            page.goto(self.FAUCET_URL, wait_until="networkidle")
            
            # Wait for faucet modal to appear or open it
            page.wait_for_timeout(2000)
            
            # Look for the faucet button in toolbar and click it
            faucet_button = page.locator('[data-ael="toolbar-faucet"], button:has-text("Faucet")').first
            try:
                faucet_button.wait_for(timeout=5000)
                faucet_button.click()
                page.wait_for_timeout(1000)
            except PlaywrightTimeout:
                # Faucet modal might already be open
                pass
            
            # Wait for the faucet modal
            modal = page.locator('.modal__title:has-text("Claim faucet"), .modal:has-text("Claim faucet")').first
            try:
                modal.wait_for(timeout=10000)
            except PlaywrightTimeout:
                result.error = "Faucet modal not found"
                return result
            
            # Select the currency if needed
            # Look for currency selector
            currency_selector = page.locator(f'[data-currency="{currency.upper()}"], button:has-text("{currency.upper()}")').first
            try:
                currency_selector.wait_for(timeout=3000)
                currency_selector.click()
                page.wait_for_timeout(500)
            except PlaywrightTimeout:
                # Currency might already be selected or selector not needed
                pass
            
            # Click the claim button
            claim_button = page.locator('button:has-text("CLAIM FAUCET"), button[data-ael="skip"]').first
            
            try:
                claim_button.wait_for(timeout=5000)
                
                # Check if button is disabled (cooldown)
                if claim_button.is_disabled():
                    # Try to get cooldown time
                    try:
                        cooldown_elem = page.locator('[data-tooltip-content*="Next faucet"]').first
                        cooldown_elem.wait_for(timeout=2000)
                        cooldown_text = cooldown_elem.get_attribute('data-tooltip-content')
                        if cooldown_text:
                            match = re.search(r'(\d+):(\d+):(\d+)', cooldown_text)
                            if match:
                                h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
                                result.cooldown_remaining = h * 3600 + m * 60 + s
                    except PlaywrightTimeout:
                        pass  # Couldn't get cooldown info, continue with default
                    result.error = f"Faucet on cooldown ({result.cooldown_remaining}s remaining)"
                    return result
                
                # Click claim button
                claim_button.click()
                self.log("Clicked claim button, waiting for result...")
                
                # Wait for success notification
                page.wait_for_timeout(3000)
                
                # Check for success toast
                toast = page.locator('.Toastify__toast--success, .notification-success').first
                try:
                    toast.wait_for(timeout=10000)
                    
                    # Extract amount from toast message
                    toast_text = toast.inner_text()
                    self.log(f"Toast message: {toast_text}")
                    
                    # Parse amount from message like "You have received free 0.00174396 SOL!"
                    match = re.search(r'(\d+\.?\d*)\s*' + currency.upper(), toast_text, re.IGNORECASE)
                    if match:
                        result.amount = match.group(1)
                    else:
                        # Try to find any number
                        match = re.search(r'(\d+\.?\d+)', toast_text)
                        if match:
                            result.amount = match.group(1)
                    
                    result.success = True
                    self.log(f"Successfully claimed {result.amount} {currency.upper()}!")
                    return result
                    
                except PlaywrightTimeout:
                    # Check for error message
                    error_toast = page.locator('.Toastify__toast--error, .notification-error').first
                    try:
                        error_toast.wait_for(timeout=2000)
                        result.error = error_toast.inner_text()
                    except PlaywrightTimeout:
                        result.error = "Unknown error - no success or error notification"
                    return result
                    
            except PlaywrightTimeout:
                result.error = "Claim button not found or not clickable"
                return result
                
        except Exception as e:
            result.error = str(e)
            self.log(f"Error claiming faucet: {e}")
        
        return result
    
    def get_available_currencies(self) -> List[str]:
        """
        Get list of currencies available for faucet claiming.
        
        Returns:
            List of currency symbols
        """
        if not self._logged_in and not self.is_logged_in():
            return []
        
        page = self._ensure_page()
        currencies = []
        
        try:
            page.goto(self.FAUCET_URL, wait_until="networkidle")
            page.wait_for_timeout(2000)
            
            # Open faucet modal
            faucet_button = page.locator('[data-ael="toolbar-faucet"], button:has-text("Faucet")').first
            try:
                faucet_button.click()
                page.wait_for_timeout(1000)
            except Exception:
                pass  # Modal might already be open
            
            # Get currencies from user balances or currency selector
            # This is implementation-specific and may need adjustment
            currency_elements = page.locator('[data-currency]').all()
            for elem in currency_elements:
                currency = elem.get_attribute('data-currency')
                if currency:
                    currencies.append(currency.upper())
            
            if not currencies:
                # Fallback: get from page content
                # Look for common crypto symbols (update as needed)
                common_currencies = ['BTC', 'ETH', 'LTC', 'DOGE', 'SOL', 'TRX', 'XRP', 'BNB', 'USDT']
                page_content = page.content()
                for curr in common_currencies:
                    if curr in page_content:
                        currencies.append(curr)
                        
        except Exception as e:
            self.log(f"Error getting currencies: {e}")
        
        return list(set(currencies))
    
    def claim_all_faucets(self) -> List[FaucetClaimResult]:
        """
        Attempt to claim faucets for all available currencies.
        
        Returns:
            List of FaucetClaimResults
        """
        results = []
        
        currencies = self.get_available_currencies()
        if not currencies:
            self.log("No currencies found for claiming")
            return results
        
        self.log(f"Found {len(currencies)} currencies to try: {', '.join(currencies)}")
        
        for currency in currencies:
            self.log(f"\nAttempting to claim {currency}...")
            result = self.claim_faucet(currency)
            results.append(result)
            
            if result.success:
                self.log(f"✓ Claimed {result.amount} {currency}")
            else:
                self.log(f"✗ Failed: {result.error}")
            
            # Wait between claims to avoid rate limiting
            time.sleep(2)
        
        return results
    
    def close(self) -> None:
        """Close browser and cleanup resources."""
        if self._page and not self._page.is_closed():
            try:
                self._page.close()
            except Exception:
                pass  # Ignore cleanup errors
            self._page = None
        
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass  # Ignore cleanup errors
            self._context = None
        
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass  # Ignore cleanup errors
            self._browser = None
        
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass  # Ignore cleanup errors
            self._playwright = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
