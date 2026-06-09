const path = require('path');
console.log('>>>>>> Webpack config loaded! <<<<<<');

module.exports = (env, argv) => {
  const isDevelopment = argv.mode === 'development';

  return {
    entry: './src/index.ts',
    output: {
      path: path.resolve(__dirname, 'dist'),
      filename: isDevelopment ? '[name].js' : '[name].[contenthash].js',
      clean: true
    },

    resolve: {
      extensions: ['.tsx', '.ts', '.jsx', '.js', '.json'],
      alias: {
        '@': path.resolve(__dirname, 'lib') //this is after tsc processed
      }
    },

    module: {
      rules: [
        {
          test: /\.(ts|tsx|js|jsx)$/,
          exclude: /node_modules/,
          use: [
            {
              loader: 'babel-loader',
              options: {
                presets: [
                  '@babel/preset-env',
                  '@babel/preset-react',
                  '@babel/preset-typescript'
                ]
              }
            },
            {
              loader: 'ts-loader',
              options: {
                transpileOnly: true
              }
            }
          ]
        },

        {
          // CSS processing (including Tailwind）
          test: /\.css$/,
          use: [
            'style-loader',
            {
              loader: 'css-loader',
              options: {
                importLoaders: 1,
                sourceMap: isDevelopment
              }
            },
            {
              loader: 'postcss-loader',
              options: {
                sourceMap: isDevelopment,
                postcssOptions: {
                  config: path.resolve(__dirname, 'postcss.config.js')
                }
              }
            }
          ]
        },

        {
          // image resource
          test: /\.(png|svg|jpg|jpeg|gif|webp)$/i,
          type: 'asset/resource'
        },

        {
          // font resource
          test: /\.(woff|woff2|eot|ttf|otf)$/i,
          type: 'asset/resource'
        }
      ]
    },

    plugins: [
      new HtmlWebpackPlugin({
        template: 'public/index.html',
        title: 'My Web App',
        favicon: false
      })
    ],

    devtool: isDevelopment ? 'eval-source-map' : 'source-map'
  };
};
