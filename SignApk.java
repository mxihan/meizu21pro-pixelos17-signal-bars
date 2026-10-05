import com.android.apksig.ApkSigner;
import com.android.apksig.ApkVerifier;
import com.android.apksig.KeyConfig;
import java.io.File;
import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.cert.X509Certificate;
import java.util.List;

class SignApk {
    public static void main(String[] args) throws Exception {
        KeyStore store = KeyStore.getInstance("PKCS12");
        try (FileInputStream input = new FileInputStream(args[0])) {
            store.load(input, "changeit".toCharArray());
        }
        PrivateKey key = (PrivateKey) store.getKey("overlay", "changeit".toCharArray());
        X509Certificate certificate = (X509Certificate) store.getCertificate("overlay");
        ApkSigner.SignerConfig signer = new ApkSigner.SignerConfig.Builder(
                "overlay", new KeyConfig.Jca(key), List.of(certificate)).build();
        File output = new File(args[2]);
        new ApkSigner.Builder(List.of(signer))
                .setInputApk(new File(args[1])).setOutputApk(output)
                .setMinSdkVersion(37)
                .setV1SigningEnabled(false).setV2SigningEnabled(true)
                .setV3SigningEnabled(true).setV4SigningEnabled(false)
                .build().sign();
        ApkVerifier.Result result = new ApkVerifier.Builder(output)
                .setMinCheckedPlatformVersion(37).build().verify();
        if (!result.isVerified()) {
            throw new IllegalStateException("APK verification failed: " + result.getErrors());
        }
        System.out.println("Signed and verified v2=" + result.isVerifiedUsingV2Scheme()
                + " v3=" + result.isVerifiedUsingV3Scheme() + ": " + output.getName());
    }
}
