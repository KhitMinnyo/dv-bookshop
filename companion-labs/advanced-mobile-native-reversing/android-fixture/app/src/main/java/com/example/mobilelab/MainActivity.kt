package com.example.mobilelab

import android.app.Activity
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val status = TextView(this).apply {
            text = "Owner-controlled reversing fixture\nEndpoint: ${RuntimeConfig.endpoint(this@MainActivity)}"
        }
        val inspect = Button(this).apply {
            text = "Check hardened configuration"
            setOnClickListener {
                status.text = try {
                    ApiClient.hardened(this@MainActivity)
                    "Hardened configuration accepted"
                } catch (error: IllegalArgumentException) {
                    "Expected local fixture result: ${error.message}"
                }
            }
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(status)
            addView(inspect)
        })
    }
}
