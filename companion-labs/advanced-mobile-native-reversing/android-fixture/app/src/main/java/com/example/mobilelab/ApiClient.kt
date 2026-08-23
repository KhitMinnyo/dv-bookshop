package com.example.mobilelab

import android.content.Context
import okhttp3.CertificatePinner
import okhttp3.OkHttpClient
import java.net.URI

object ApiClient {
    fun vulnerable(context: Context): OkHttpClient {
        // Vulnerable teaching example: a client secret is shipped in the app.
        val shippedSecret = RuntimeConfig.SHIPPED_CLIENT_SECRET
        check(shippedSecret.isNotEmpty())
        return OkHttpClient.Builder().build()
    }

    fun hardened(context: Context): OkHttpClient {
        val endpoint = URI(RuntimeConfig.endpoint(context))
        require(endpoint.scheme == "https") { "The hardened client requires HTTPS" }

        // Replace this fake pin only during a controlled local exercise.
        val pinner = CertificatePinner.Builder()
            .add(endpoint.host, "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
            .build()

        return OkHttpClient.Builder()
            .certificatePinner(pinner)
            .build()
    }
}
