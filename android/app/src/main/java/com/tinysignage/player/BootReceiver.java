package com.tinysignage.player;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

/**
 * Receives BOOT_COMPLETED broadcast and auto-launches the player
 * if a server URL has been configured.
 */
public class BootReceiver extends BroadcastReceiver {

    private static final String PREFS_NAME = "tinysignage";
    private static final String KEY_SERVER_URL = "server_url";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
            String serverUrl = prefs.getString(KEY_SERVER_URL, null);

            if (serverUrl != null && !serverUrl.isEmpty()) {
                // Server configured — launch directly to player
                Intent launch = new Intent(context, MainActivity.class);
                launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(launch);
            } else {
                // No server yet — launch setup
                Intent launch = new Intent(context, SetupActivity.class);
                launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(launch);
            }
        }
    }
}
