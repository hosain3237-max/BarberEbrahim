package ir.ebrahim.salon;

import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.net.Uri;
import android.webkit.*;
import android.widget.*;
import android.view.WindowInsets;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseOptions;
import com.google.firebase.messaging.FirebaseMessaging;

public class MainActivity extends Activity {
    private volatile String token = "";
    private boolean firebase;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        String id=getString(R.string.salon_firebase_app_id);
        if (!id.isEmpty()) {
            FirebaseApp.initializeApp(this,new FirebaseOptions.Builder().setApplicationId(id)
                .setApiKey(getString(R.string.salon_firebase_api_key)).setProjectId(getString(R.string.salon_firebase_project_id))
                .setGcmSenderId(getString(R.string.salon_firebase_sender_id)).build());
            firebase=true;
            ReminderService.channel(this);
            if (Build.VERSION.SDK_INT>=33 && checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)!=0)
                requestPermissions(new String[]{android.Manifest.permission.POST_NOTIFICATIONS},1);
        }
        if (BuildConfig.SALON_URL.equals("https://example.invalid/")) {
            TextView info=new TextView(this); info.setPadding(32,96,32,32);
            info.setText("ابتدا نشانی سرور آرایشگاه را در تنظیمات ساخت وارد کنید."); setContentView(info); return;
        }
        Uri origin=Uri.parse(BuildConfig.SALON_URL);
        WebView web=new WebView(this);
        web.setOnApplyWindowInsetsListener((v,insets)->{
            if(Build.VERSION.SDK_INT>=30){android.graphics.Insets b=insets.getInsets(WindowInsets.Type.systemBars()); v.setPadding(b.left,b.top,b.right,b.bottom);} return insets;
        });
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.addJavascriptInterface(new Object(){@JavascriptInterface public String token(){return token;}},"SalonAndroid");
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri u=request.getUrl(); return !"https".equals(u.getScheme()) || !origin.getHost().equals(u.getHost()) || origin.getPort()!=u.getPort();
            }
            @Override public void onReceivedHttpAuthRequest(WebView view,HttpAuthHandler handler,String host,String realm){
                if(!origin.getHost().equals(host)){handler.cancel();return;}
                EditText input=new EditText(MainActivity.this); input.setInputType(129);
                new android.app.AlertDialog.Builder(MainActivity.this).setTitle("رمز مدیر آرایشگاه").setView(input)
                    .setPositiveButton("ورود",(d,w)->handler.proceed("admin",input.getText().toString()))
                    .setNegativeButton("انصراف",(d,w)->handler.cancel()).setOnCancelListener(d->handler.cancel()).show();
            }
        });
        setContentView(web);web.loadUrl(BuildConfig.SALON_URL);
    }
    @Override public void onResume(){super.onResume();if(firebase)FirebaseMessaging.getInstance().getToken().addOnSuccessListener(t->token=t);}
}
