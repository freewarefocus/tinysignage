package com.tinysignage.player;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.net.http.SslError;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import android.text.InputType;
import android.widget.EditText;

/**
 * Fullscreen WebView kiosk that loads the TinySignage player page.
 * Handles SSL errors for self-signed certs, network retries,
 * admin escape gesture, and immersive mode.
 */
public class MainActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "tinysignage";
    private static final String KEY_SERVER_URL = "server_url";
    private static final String KEY_ADMIN_PIN = "admin_pin";
    private static final String DEFAULT_PIN = "0000";
    private static final long RETRY_DELAY_MS = 10000;
    private static final String USER_AGENT_SUFFIX = " TinySignageApp/1.0";

    // Admin escape: triple-tap top-right corner
    private static final int TAP_COUNT_REQUIRED = 3;
    private static final long TAP_WINDOW_MS = 1500;
    private static final float TAP_ZONE_FRACTION = 0.15f;

    private WebView webView;
    private Handler handler;
    private String serverUrl;
    private int tapCount = 0;
    private long lastTapTime = 0;
    private boolean loadError = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        KioskHelper.enterKioskMode(this);

        setContentView(R.layout.activity_main);

        handler = new Handler(Looper.getMainLooper());
        serverUrl = getServerUrl();

        if (serverUrl == null || serverUrl.isEmpty()) {
            // No server configured — go back to setup
            startActivity(new Intent(this, SetupActivity.class));
            finish();
            return;
        }

        webView = findViewById(R.id.webView);
        configureWebView();
        loadPlayer();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = webView.getSettings();

        // Core settings for player.js
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);

        // Media autoplay
        settings.setMediaPlaybackRequiresUserGesture(false);

        // Custom user-agent so player.js can detect Android app
        String defaultUA = settings.getUserAgentString();
        settings.setUserAgentString(defaultUA + USER_AGENT_SUFFIX);

        // Allow mixed content (HTTP resources on HTTPS pages)
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        // Cache settings
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new SignageWebViewClient());

        // Black background while loading
        webView.setBackgroundColor(0xFF000000);
    }

    private void loadPlayer() {
        loadError = false;
        String playerUrl = serverUrl + "/player";
        webView.loadUrl(playerUrl);
    }

    // --- Admin escape gesture: triple-tap top-right corner ---

    @Override
    public boolean dispatchTouchEvent(MotionEvent event) {
        if (event.getAction() == MotionEvent.ACTION_DOWN) {
            float x = event.getX();
            float y = event.getY();
            int width = getWindow().getDecorView().getWidth();

            // Check if tap is in top-right corner
            if (x > width * (1 - TAP_ZONE_FRACTION) && y < width * TAP_ZONE_FRACTION) {
                long now = System.currentTimeMillis();
                if (now - lastTapTime > TAP_WINDOW_MS) {
                    tapCount = 0;
                }
                tapCount++;
                lastTapTime = now;

                if (tapCount >= TAP_COUNT_REQUIRED) {
                    tapCount = 0;
                    showPinDialog();
                }
            } else {
                tapCount = 0;
            }
        }
        return super.dispatchTouchEvent(event);
    }

    private void showPinDialog() {
        EditText pinInput = new EditText(this);
        pinInput.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        pinInput.setHint("Enter admin PIN");
        pinInput.setPadding(48, 32, 48, 32);

        new AlertDialog.Builder(this)
                .setTitle("Admin Access")
                .setMessage("Enter PIN to access settings")
                .setView(pinInput)
                .setPositiveButton("OK", (dialog, which) -> {
                    String pin = pinInput.getText().toString();
                    String savedPin = getAdminPin();
                    if (pin.equals(savedPin)) {
                        showAdminMenu();
                    } else {
                        Toast.makeText(this, "Incorrect PIN", Toast.LENGTH_SHORT).show();
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void showAdminMenu() {
        String[] options = {"Change Server URL", "Change PIN", "Reload Player", "Exit App"};

        new AlertDialog.Builder(this)
                .setTitle("Admin Menu")
                .setItems(options, (dialog, which) -> {
                    switch (which) {
                        case 0: changeServerUrl(); break;
                        case 1: changePin(); break;
                        case 2: loadPlayer(); break;
                        case 3: finishAndRemoveTask(); break;
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private void changeServerUrl() {
        // Clear saved URL and go to setup
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        prefs.edit().remove(KEY_SERVER_URL).apply();
        startActivity(new Intent(this, SetupActivity.class));
        finish();
    }

    private void changePin() {
        EditText pinInput = new EditText(this);
        pinInput.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        pinInput.setHint("New 4-digit PIN");
        pinInput.setPadding(48, 32, 48, 32);

        new AlertDialog.Builder(this)
                .setTitle("Set New PIN")
                .setView(pinInput)
                .setPositiveButton("Save", (dialog, which) -> {
                    String newPin = pinInput.getText().toString();
                    if (newPin.length() >= 4) {
                        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
                        prefs.edit().putString(KEY_ADMIN_PIN, newPin).apply();
                        Toast.makeText(this, "PIN updated", Toast.LENGTH_SHORT).show();
                    } else {
                        Toast.makeText(this, "PIN must be at least 4 digits", Toast.LENGTH_SHORT).show();
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    // --- WebView client with SSL + retry handling ---

    private class SignageWebViewClient extends WebViewClient {

        @Override
        public void onPageStarted(WebView view, String url, Bitmap favicon) {
            super.onPageStarted(view, url, favicon);
            loadError = false;
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            // Only handle errors for the main frame
            if (request.isForMainFrame()) {
                loadError = true;
                scheduleRetry();
            }
        }

        @Override
        public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
            // Accept self-signed certs only for our configured server
            String errorUrl = error.getUrl();
            if (serverUrl != null && errorUrl != null && errorUrl.startsWith(serverUrl)) {
                handler.proceed();
            } else {
                handler.cancel();
            }
        }
    }

    private void scheduleRetry() {
        handler.postDelayed(() -> {
            if (loadError) {
                loadPlayer();
            }
        }, RETRY_DELAY_MS);
    }

    // --- Kiosk behavior ---

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            KioskHelper.enterKioskMode(this);
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        // Block back button in kiosk mode
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onResume() {
        super.onResume();
        KioskHelper.enterKioskMode(this);
        if (webView != null) {
            webView.onResume();
        }
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            webView.onPause();
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    // --- Preferences helpers ---

    private String getServerUrl() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        return prefs.getString(KEY_SERVER_URL, null);
    }

    private String getAdminPin() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        return prefs.getString(KEY_ADMIN_PIN, DEFAULT_PIN);
    }
}
