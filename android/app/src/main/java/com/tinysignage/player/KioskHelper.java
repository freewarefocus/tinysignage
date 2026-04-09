package com.tinysignage.player;

import android.app.Activity;
import android.os.Build;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;

/**
 * Utility for entering immersive sticky fullscreen mode
 * and keeping the screen on. Handles both modern (API 30+)
 * and legacy approaches.
 */
public class KioskHelper {

    private KioskHelper() {}

    /**
     * Enter fullscreen immersive mode and keep the screen on.
     * Call from onCreate, onResume, and onWindowFocusChanged.
     */
    public static void enterKioskMode(Activity activity) {
        keepScreenOn(activity);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            // API 30+ — WindowInsetsController
            enterImmersiveModern(activity);
        } else {
            // API 24-29 — legacy system UI flags
            enterImmersiveLegacy(activity);
        }
    }

    private static void keepScreenOn(Activity activity) {
        activity.getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @SuppressWarnings("deprecation")
    private static void enterImmersiveLegacy(Activity activity) {
        View decorView = activity.getWindow().getDecorView();
        decorView.setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
        );
    }

    private static void enterImmersiveModern(Activity activity) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            WindowInsetsController controller = activity.getWindow().getInsetsController();
            if (controller != null) {
                controller.hide(WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars());
                controller.setSystemBarsBehavior(
                        WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                );
            }
        }
    }
}
