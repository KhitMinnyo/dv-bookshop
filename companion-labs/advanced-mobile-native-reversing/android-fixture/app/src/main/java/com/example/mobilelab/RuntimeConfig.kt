package com.example.mobilelab

import android.content.Context

object RuntimeConfig {
    // Deliberately fake values for decompilation practice. These are not secrets.
    const val SHIPPED_PUBLIC_API_KEY = "demo-public-key-DO-NOT-USE"
    const val SHIPPED_CLIENT_SECRET = "demo-client-secret-DO-NOT-USE"
    private const val DEFAULT_ENDPOINT = "https://lab.invalid/api"

    fun endpoint(context: Context): String {
        // A debuggable local exercise can override this with an app property.
        return context.getSharedPreferences("lab", Context.MODE_PRIVATE)
            .getString("runtimeEndpoint", DEFAULT_ENDPOINT)
            ?: DEFAULT_ENDPOINT
    }
}
