# Keep Kotlin/Retrofit/Gson metadata required for reflective API serialization.
-keepattributes Signature,InnerClasses,EnclosingMethod
-keepattributes RuntimeVisibleAnnotations,RuntimeInvisibleAnnotations
-keepattributes RuntimeVisibleParameterAnnotations,RuntimeInvisibleParameterAnnotations
-keepattributes AnnotationDefault

# Gson uses the Kotlin backing-field names as the JSON contract.
-keep class com.thirdhand.app.**Dto {
    <fields>;
}

# Retrofit reads endpoint and parameter annotations from this interface at runtime.
-keep interface com.thirdhand.app.ThirdHandApi {
    *;
}
