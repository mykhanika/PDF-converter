package com.pdftoolkit.app

import android.app.Activity
import android.app.AlertDialog
import android.app.DownloadManager
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.view.Menu
import android.view.MenuItem
import android.webkit.*
import android.widget.EditText
import android.widget.Toast

/** Thin shell that shows the PDF Toolkit server in a full-screen WebView. */
class MainActivity : Activity() {
    private lateinit var web: WebView
    private var chooser: ValueCallback<Array<Uri>>? = null
    private val prefs by lazy { getSharedPreferences("pdftoolkit", MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        setContentView(web)
        web.settings.apply { javaScriptEnabled = true; domStorageEnabled = true; allowFileAccess = false }
        CookieManager.getInstance().setAcceptCookie(true)

        web.webViewClient = object : WebViewClient() {
            override fun onReceivedError(v: WebView?, r: WebResourceRequest?, e: WebResourceError?) {
                if (r?.isForMainFrame == true) askServer("Cannot reach the server. Check the address and Wi-Fi.")
            }
        }
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(w: WebView?, cb: ValueCallback<Array<Uri>>?, p: FileChooserParams?): Boolean {
                chooser?.onReceiveValue(null); chooser = cb
                return try { startActivityForResult(p!!.createIntent(), 1); true } catch (e: Exception) { chooser = null; false }
            }
        }
        web.setDownloadListener { url, ua, cd, mime, _ ->
            val name = URLUtil.guessFileName(url, cd, mime)
            val req = DownloadManager.Request(Uri.parse(url))
                .addRequestHeader("Cookie", CookieManager.getInstance().getCookie(url) ?: "")
                .addRequestHeader("User-Agent", ua)
                .setTitle(name)
                .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name)
            (getSystemService(DOWNLOAD_SERVICE) as DownloadManager).enqueue(req)
            Toast.makeText(this, "Downloading $name to your Downloads folder", Toast.LENGTH_LONG).show()
        }

        val saved = prefs.getString("url", null)
        if (saved == null) askServer(null) else web.loadUrl(saved)
    }

    private fun askServer(message: String?) {
        val box = EditText(this).apply {
            hint = "http://192.168.1.5:5000/?key=..."
            setText(prefs.getString("url", "http://"))
            setSingleLine()
        }
        AlertDialog.Builder(this)
            .setTitle("PDF Toolkit server")
            .setMessage(message ?: "Enter the address of your PDF Toolkit server (shown when you start it).")
            .setView(box)
            .setCancelable(prefs.getString("url", null) != null)
            .setPositiveButton("Connect") { _, _ ->
                var u = box.text.toString().trim()
                if (!u.startsWith("http")) u = "http://$u"
                prefs.edit().putString("url", u).apply()
                web.loadUrl(u)
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    override fun onActivityResult(req: Int, res: Int, data: Intent?) {
        if (req == 1) {
            chooser?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(res, data))
            chooser = null
        } else super.onActivityResult(req, res, data)
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menu.add(0, 1, 0, "Change server"); menu.add(0, 2, 1, "Reload"); return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == 1) askServer(null) else if (item.itemId == 2) web.reload()
        return true
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() { if (web.canGoBack()) web.goBack() else super.onBackPressed() }
}
